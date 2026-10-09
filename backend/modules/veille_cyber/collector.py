"""Daily collection: KEV + new critical CVEs, enriched with NVD and EPSS, then summarized."""

import logging
from datetime import date, datetime, timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.collect import CollectContext
from modules.veille_cyber.digest import (
    DIGEST_SYSTEM,
    SHEET_SYSTEM,
    digest_prompt,
    priority,
    sheet_prompt,
)
from modules.veille_cyber.models import Digest, ProductSheet, Vulnerability
from modules.veille_cyber.skills import is_known, load_skills, product_key
from modules.veille_cyber.sources.epss import fetch_epss
from modules.veille_cyber.sources.kev import KevEntry, fetch_kev
from modules.veille_cyber.sources.nvd import NvdClient, NvdCve

logger = logging.getLogger(__name__)

MAX_NVD_LOOKUPS = 50  # KEV entries enriched per run (6 s each without an NVD key)
MAX_SHEETS_PER_RUN = 5  # caps the Claude cost of product sheets


def collect(ctx: CollectContext) -> dict[str, int]:
    db, now = ctx.db, ctx.now
    since = ctx.last_success_at or now - timedelta(days=1)
    api_key = ctx.settings.nvd_api_key
    nvd = NvdClient(ctx.http, api_key.get_secret_value() if api_key else None)

    new_kev = _sync_kev(db, fetch_kev(ctx.http), now, first_run=ctx.last_success_at is None)
    for cve_id in new_kev[:MAX_NVD_LOOKUPS]:
        if cve := nvd.get_cve(cve_id):
            _apply_nvd(db, cve, now)

    critical = nvd.critical_published(since, now)
    for cve in critical:
        _apply_nvd(db, cve, now)

    new_ids = list(dict.fromkeys(new_kev + [c.cve_id for c in critical]))
    for cve_id, score in fetch_epss(ctx.http, new_ids).items():
        if vuln := db.get(Vulnerability, cve_id):
            vuln.epss, vuln.epss_percentile = score.epss, score.percentile
    db.commit()

    day_vulns = _update_digest_items(ctx, now.date(), new_ids)
    summarized = _summarize(ctx, now.date(), day_vulns)
    # Whole day, not just this run: products skipped by the cap get their sheet next run.
    sheets = _write_sheets(ctx, day_vulns)
    return {
        "new_kev": len(new_kev),
        "new_critical": len(critical),
        "digest": int(summarized),
        "sheets": sheets,
    }


def _sync_kev(db: Session, entries: list[KevEntry], now: datetime, first_run: bool) -> list[str]:
    """Upsert the whole catalog; return the CVE ids that are new for us."""
    known = set(db.scalars(select(Vulnerability.cve_id).where(Vulnerability.in_kev)))
    recent = now.date() - timedelta(days=1)
    new_ids = []
    for entry in entries:
        vuln = db.get(Vulnerability, entry.cve_id)
        if vuln is None:
            vuln = Vulnerability(cve_id=entry.cve_id, first_seen_at=now, description="")
            db.add(vuln)
        vuln.vendor, vuln.product, vuln.title = entry.vendor, entry.product, entry.name
        vuln.description = vuln.description or entry.description
        vuln.in_kev, vuln.ransomware = True, entry.ransomware
        vuln.kev_date_added, vuln.kev_due_date = entry.date_added, entry.due_date
        vuln.updated_at = now
        # First run: the whole catalog is loaded, but only the last day counts as "new".
        if entry.cve_id not in known and (not first_run or entry.date_added >= recent):
            new_ids.append(entry.cve_id)
    return new_ids


def _apply_nvd(db: Session, cve: NvdCve, now: datetime) -> None:
    vuln = db.get(Vulnerability, cve.cve_id)
    if vuln is None:
        vuln = Vulnerability(cve_id=cve.cve_id, first_seen_at=now, in_kev=False, ransomware=False)
        db.add(vuln)
    vuln.description = cve.description or vuln.description or ""
    vuln.published = cve.published
    vuln.cvss_score, vuln.cvss_severity = cve.cvss_score, cve.cvss_severity
    vuln.cvss_version = cve.cvss_version
    # KEV names the product better than CPE ("Apache Log4j2" vs "log4j").
    vuln.vendor = vuln.vendor or cve.vendor
    vuln.product = vuln.product or cve.product
    vuln.updated_at = now


def _update_digest_items(ctx: CollectContext, day: date, new_ids: list[str]) -> list[Vulnerability]:
    """Add this run's CVEs to the day's digest; return all of the day's vulnerabilities."""
    digest = ctx.db.get(Digest, day) or Digest(day=day, cve_ids=[], created_at=ctx.now)
    # Several runs on the same day add up instead of replacing each other.
    digest.cve_ids = list(dict.fromkeys(digest.cve_ids + new_ids))
    digest.created_at = ctx.now
    ctx.db.add(digest)
    ctx.db.commit()
    return [v for cve_id in digest.cve_ids if (v := ctx.db.get(Vulnerability, cve_id))]


def _summarize(ctx: CollectContext, day: date, vulns: list[Vulnerability]) -> bool:
    if not vulns or not ctx.llm.enabled:
        return False
    text = ctx.llm.complete("veille_cyber.digest", DIGEST_SYSTEM, digest_prompt(vulns))
    if text:
        ctx.db.get(Digest, day).text = text
        ctx.db.commit()
    return text is not None


def _write_sheets(ctx: CollectContext, vulns: list[Vulnerability]) -> int:
    if not ctx.llm.enabled:
        return 0
    skills = load_skills(ctx.settings.skills_file)
    if skills is None:
        return 0
    written = 0
    for vuln in sorted(vulns, key=priority):
        if written >= MAX_SHEETS_PER_RUN:
            break
        if not vuln.product or is_known(skills, vuln.vendor, vuln.product):
            continue
        key = product_key(vuln.vendor, vuln.product)
        if ctx.db.get(ProductSheet, key):
            continue
        text = ctx.llm.complete(
            "veille_cyber.sheet", SHEET_SYSTEM, sheet_prompt(vuln.vendor, vuln.product)
        )
        if text:
            ctx.db.add(
                ProductSheet(
                    product_key=key,
                    vendor=vuln.vendor,
                    product=vuln.product,
                    text=text,
                    created_at=ctx.now,
                )
            )
            ctx.db.commit()
            written += 1
    return written
