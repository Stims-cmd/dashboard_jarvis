"""Read-only API of the OSINT window (mounted under /api/modules/osint)."""

from datetime import UTC, date, datetime, timedelta
from typing import Literal

from fastapi import APIRouter, Query
from pydantic import BaseModel, ConfigDict
from sqlalchemy import select

from app.core_models import CollectorRun
from app.deps import AppSettings, DbSession
from modules.osint.models import Finding, Report

router = APIRouter()

STALE_AFTER = timedelta(days=8)  # weekly collection + margin


class FindingOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    kind: str
    subject: str
    source: str
    key: str
    title: str
    details: dict
    first_seen_at: datetime
    last_seen_at: datetime


class ReportOut(BaseModel):
    week: date
    created_at: datetime
    sources: dict[str, str]
    new_findings: list[FindingOut]


class StatusOut(BaseModel):
    last_success_at: datetime | None
    last_run_status: str | None
    stale: bool
    targets_file_found: bool
    brave_enabled: bool
    total_findings: int


def _utc(value: datetime | None) -> datetime | None:
    # SQLite does not keep timezone info: stored values are UTC.
    return value.replace(tzinfo=UTC) if value and value.tzinfo is None else value


def _out(finding: Finding) -> FindingOut:
    out = FindingOut.model_validate(finding)
    out.first_seen_at = _utc(out.first_seen_at)
    out.last_seen_at = _utc(out.last_seen_at)
    return out


@router.get("/status")
def status(db: DbSession, settings: AppSettings) -> StatusOut:
    runs = select(CollectorRun).where(CollectorRun.module == "osint")
    last = db.scalars(runs.order_by(CollectorRun.started_at.desc()).limit(1)).first()
    last_ok = db.scalars(
        runs.where(CollectorRun.status == "ok").order_by(CollectorRun.started_at.desc()).limit(1)
    ).first()
    last_success_at = _utc(last_ok.started_at) if last_ok else None
    return StatusOut(
        last_success_at=last_success_at,
        last_run_status=last.status if last else None,
        stale=last_success_at is None or datetime.now(UTC) - last_success_at > STALE_AFTER,
        targets_file_found=settings.osint_file.is_file(),
        brave_enabled=settings.brave_api_key is not None,
        total_findings=len(db.scalars(select(Finding.id)).all()),
    )


@router.get("/report/latest")
def latest_report(db: DbSession) -> ReportOut | None:
    report = db.scalars(select(Report).order_by(Report.week.desc()).limit(1)).first()
    if report is None:
        return None
    findings = []
    if report.new_finding_ids:
        query = select(Finding).where(Finding.id.in_(report.new_finding_ids))
        findings = [_out(f) for f in db.scalars(query.order_by(Finding.kind, Finding.id))]
    return ReportOut(
        week=report.week,
        created_at=_utc(report.created_at),
        sources=report.sources,
        new_findings=findings,
    )


@router.get("/findings")
def findings(
    db: DbSession,
    kind: Literal["breach", "mention", "account", "gravatar"] | None = Query(default=None),
) -> list[FindingOut]:
    query = select(Finding).order_by(Finding.first_seen_at.desc(), Finding.id.desc()).limit(500)
    if kind is not None:
        query = query.where(Finding.kind == kind)
    return [_out(f) for f in db.scalars(query)]
