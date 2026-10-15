"""Read-only API of the Leboncoin window (mounted under /api/modules/leboncoin)."""

from datetime import UTC, datetime, timedelta

from fastapi import APIRouter, Query
from pydantic import BaseModel, ConfigDict
from sqlalchemy import func, select

from app.core_models import CollectorRun
from app.deps import AppSettings, DbSession
from modules.leboncoin.analysis_routes import router as analysis_router
from modules.leboncoin.mailbox import ImapConfig
from modules.leboncoin.models import Ad
from modules.leboncoin.sales_routes import router as sales_router

router = APIRouter()
router.include_router(sales_router)
router.include_router(analysis_router)

STALE_AFTER = timedelta(hours=3)  # hourly collection + margin


class AdOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    ad_id: str
    search_name: str
    title: str
    price_cents: int | None
    location: str
    url: str
    price_history: list[tuple[str, int | None]]
    first_seen_at: datetime
    last_seen_at: datetime


class SearchOut(BaseModel):
    name: str
    ads: int


class StatusOut(BaseModel):
    last_success_at: datetime | None
    last_run_status: str | None
    stale: bool
    imap_configured: bool
    total_ads: int


def _utc(value: datetime | None) -> datetime | None:
    # SQLite does not keep timezone info: stored values are UTC.
    return value.replace(tzinfo=UTC) if value and value.tzinfo is None else value


def _out(ad: Ad) -> AdOut:
    out = AdOut.model_validate(ad)
    out.first_seen_at = _utc(out.first_seen_at)
    out.last_seen_at = _utc(out.last_seen_at)
    return out


@router.get("/status")
def status(db: DbSession, settings: AppSettings) -> StatusOut:
    runs = select(CollectorRun).where(CollectorRun.module == "leboncoin")
    last = db.scalars(runs.order_by(CollectorRun.started_at.desc()).limit(1)).first()
    last_ok = db.scalars(
        runs.where(CollectorRun.status == "ok").order_by(CollectorRun.started_at.desc()).limit(1)
    ).first()
    last_success_at = _utc(last_ok.started_at) if last_ok else None
    return StatusOut(
        last_success_at=last_success_at,
        last_run_status=last.status if last else None,
        stale=last_success_at is None or datetime.now(UTC) - last_success_at > STALE_AFTER,
        imap_configured=ImapConfig.from_settings(settings) is not None,
        total_ads=db.scalar(select(func.count(Ad.id))) or 0,
    )


@router.get("/ads")
def ads(
    db: DbSession,
    search: str | None = Query(default=None, max_length=200),
    limit: int = Query(default=200, ge=1, le=500),
) -> list[AdOut]:
    query = select(Ad).order_by(Ad.first_seen_at.desc(), Ad.id.desc()).limit(limit)
    if search is not None:
        query = query.where(Ad.search_name == search)
    return [_out(ad) for ad in db.scalars(query)]


@router.get("/searches")
def searches(db: DbSession) -> list[SearchOut]:
    rows = db.execute(
        select(Ad.search_name, func.count(Ad.id)).group_by(Ad.search_name).order_by(Ad.search_name)
    )
    return [SearchOut(name=name, ads=count) for name, count in rows]
