"""Weekly OSINT collection about the owner only.

Logs never contain identifiers: only source names, error types and counters.
"""

import logging
import time
from collections.abc import Callable, Iterable
from datetime import date, timedelta

from sqlalchemy import select

from app.collect import CollectContext
from modules.osint.config import load_targets, phone_variants
from modules.osint.models import Finding, Report
from modules.osint.sources import RawFinding, brave, gravatar, xon
from modules.osint.sources.platforms import PLATFORMS, check_username

logger = logging.getLogger(__name__)

PAUSE_SECONDS = 1.0  # between two calls to the same kind of API


def week_of(day: date) -> date:
    return day - timedelta(days=day.weekday())


class _SourceRunner:
    """Runs calls source by source; a failing source never stops the others."""

    def __init__(self) -> None:
        self.findings: list[RawFinding] = []
        self.status: dict[str, str] = {}

    def disable(self, source: str) -> None:
        self.status[source] = "disabled"

    def run(self, source: str, call: Callable[[], Iterable[RawFinding] | RawFinding | None]):
        self.status.setdefault(source, "ok")
        try:
            result = call()
        except Exception as error:  # noqa: BLE001 - any failure is reported, not raised
            # Exception messages can contain the requested URL, hence the email: type only.
            logger.warning("osint source %s failed: %s", source, type(error).__name__)
            self.status[source] = "error"
            return
        finally:
            time.sleep(PAUSE_SECONDS)
        if isinstance(result, RawFinding):
            self.findings.append(result)
        elif result:
            self.findings.extend(result)


def collect(ctx: CollectContext) -> dict[str, int]:
    targets = load_targets(ctx.settings.osint_file)
    if targets is None:
        return {"skipped": 1}

    runner = _SourceRunner()
    for email in targets.emails:
        subject = f"e-mail {email.label}"
        runner.run(
            "xposedornot", lambda e=email, s=subject: xon.fetch_breaches(ctx.http, e.value, s)
        )
        runner.run(
            "gravatar", lambda e=email, s=subject: gravatar.check_profile(ctx.http, e.value, s)
        )

    for username in targets.usernames:
        for platform in PLATFORMS:
            runner.run("platforms", lambda p=platform, u=username: check_username(ctx.http, p, u))

    key = ctx.settings.brave_api_key
    if key is None:
        runner.disable("brave")
    else:
        queries = [(name, "nom") for name in targets.names] + [
            (variant, f"téléphone {phone.label}")
            for phone in targets.phones
            for variant in phone_variants(phone.value)
        ]
        for query, subject in queries:
            runner.run(
                "brave",
                lambda q=query, s=subject: brave.search(ctx.http, key.get_secret_value(), q, s),
            )

    new_ids = _store(ctx, runner.findings)
    _write_report(ctx, new_ids, runner.status)
    errors = sum(1 for status in runner.status.values() if status == "error")
    logger.info(
        "osint: %d findings, %d new, %d source errors", len(runner.findings), len(new_ids), errors
    )
    return {"findings": len(runner.findings), "new": len(new_ids), "source_errors": errors}


def _store(ctx: CollectContext, raw_findings: list[RawFinding]) -> list[int]:
    new_ids = []
    for raw in {(r.kind, r.subject, r.key): r for r in raw_findings}.values():
        finding = ctx.db.scalar(
            select(Finding).where(
                Finding.kind == raw.kind, Finding.subject == raw.subject, Finding.key == raw.key
            )
        )
        if finding is None:
            finding = Finding(
                kind=raw.kind,
                subject=raw.subject,
                source=raw.source,
                key=raw.key,
                title=raw.title,
                details=raw.details,
                first_seen_at=ctx.now,
                last_seen_at=ctx.now,
            )
            ctx.db.add(finding)
            ctx.db.flush()  # assigns the id
            new_ids.append(finding.id)
        finding.title = raw.title
        finding.details = raw.details
        finding.last_seen_at = ctx.now
    ctx.db.commit()
    return new_ids


def _write_report(ctx: CollectContext, new_ids: list[int], status: dict[str, str]) -> None:
    week = week_of(ctx.now.date())
    report = ctx.db.get(Report, week) or Report(week=week, new_finding_ids=[])
    # Several runs in the same week add up.
    report.new_finding_ids = list(dict.fromkeys(report.new_finding_ids + new_ids))
    report.sources = status
    report.created_at = ctx.now
    ctx.db.add(report)
    ctx.db.commit()
