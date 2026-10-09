"""Read-only API of the Veille cyber window (mounted under /api/modules/veille_cyber)."""

from datetime import UTC, date, datetime, timedelta

from fastapi import APIRouter, Query
from pydantic import BaseModel, ConfigDict
from sqlalchemy import func, select

from app.core_models import CollectorRun, LlmCall
from app.deps import AppSettings, DbSession
from modules.veille_cyber.digest import priority
from modules.veille_cyber.models import Digest, ProductSheet, Vulnerability

router = APIRouter()

STALE_AFTER = timedelta(hours=36)  # daily collection + margin


class RunOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    started_at: datetime
    finished_at: datetime | None
    status: str
    summary: str | None


class StatusOut(BaseModel):
    last_run: RunOut | None
    last_success_at: datetime | None
    stale: bool  # no successful collection for more than 36 h
    llm_enabled: bool
    skills_file_found: bool
    llm_cost_month_usd: float


class VulnerabilityOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    cve_id: str
    vendor: str | None
    product: str | None
    title: str | None
    description: str
    published: datetime | None
    cvss_score: float | None
    cvss_severity: str | None
    cvss_version: str | None
    epss: float | None
    epss_percentile: float | None
    in_kev: bool
    kev_date_added: date | None
    kev_due_date: date | None
    ransomware: bool


class DigestOut(BaseModel):
    day: date
    text: str | None
    vulnerabilities: list[VulnerabilityOut]


class SheetOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    vendor: str | None
    product: str
    text: str
    created_at: datetime


def _utc(value: datetime | None) -> datetime | None:
    # SQLite does not keep timezone info: stored values are UTC.
    return value.replace(tzinfo=UTC) if value and value.tzinfo is None else value


def _vulnerabilities(db: DbSession, cve_ids: list[str]) -> list[Vulnerability]:
    if not cve_ids:
        return []
    found = db.scalars(select(Vulnerability).where(Vulnerability.cve_id.in_(cve_ids)))
    return sorted(found, key=priority)


@router.get("/status")
def status(db: DbSession, settings: AppSettings) -> StatusOut:
    runs = select(CollectorRun).where(CollectorRun.module == "veille_cyber")
    last_run = db.scalars(runs.order_by(CollectorRun.started_at.desc()).limit(1)).first()
    last_ok = db.scalars(
        runs.where(CollectorRun.status == "ok").order_by(CollectorRun.started_at.desc()).limit(1)
    ).first()
    month_start = datetime.now(UTC).replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    cost = db.scalar(
        select(func.coalesce(func.sum(LlmCall.cost_usd), 0.0)).where(
            LlmCall.created_at >= month_start
        )
    )
    run_out = None
    if last_run:
        run_out = RunOut.model_validate(last_run)
        run_out.started_at = _utc(run_out.started_at)
        run_out.finished_at = _utc(run_out.finished_at)
    last_success_at = _utc(last_ok.started_at) if last_ok else None
    return StatusOut(
        last_run=run_out,
        last_success_at=last_success_at,
        stale=last_success_at is None or datetime.now(UTC) - last_success_at > STALE_AFTER,
        llm_enabled=settings.anthropic_api_key is not None,
        skills_file_found=settings.skills_file.is_file(),
        llm_cost_month_usd=round(cost or 0.0, 4),
    )


@router.get("/digest/latest")
def latest_digest(db: DbSession) -> DigestOut | None:
    digest = db.scalars(select(Digest).order_by(Digest.day.desc()).limit(1)).first()
    if digest is None:
        return None
    return DigestOut(
        day=digest.day,
        text=digest.text,
        vulnerabilities=_vulnerabilities(db, digest.cve_ids),
    )


@router.get("/vulnerabilities")
def recent_vulnerabilities(
    db: DbSession, days: int = Query(default=7, ge=1, le=90)
) -> list[VulnerabilityOut]:
    since = datetime.now(UTC).date() - timedelta(days=days - 1)
    digests = db.scalars(select(Digest).where(Digest.day >= since))
    cve_ids = list(dict.fromkeys(cve_id for d in digests for cve_id in d.cve_ids))
    return _vulnerabilities(db, cve_ids)


@router.get("/sheets")
def sheets(db: DbSession) -> list[SheetOut]:
    query = select(ProductSheet).order_by(ProductSheet.created_at.desc()).limit(50)
    return list(db.scalars(query))
