"""Read-only API of the Veille cyber window (mounted under /api/modules/veille_cyber)."""

from datetime import UTC, date, datetime, timedelta

from fastapi import APIRouter, Query
from pydantic import BaseModel, ConfigDict
from sqlalchemy import func, select

from app.core_models import CollectorRun, LlmCall
from app.deps import AppSettings, DbSession
from modules.veille_cyber.collector import day_articles
from modules.veille_cyber.models import Article, Digest
from modules.veille_cyber.sources.feeds import FEEDS

router = APIRouter()

STALE_AFTER = timedelta(hours=18)  # two collections a day + margin


class RunOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    started_at: datetime
    finished_at: datetime | None
    status: str
    summary: str | None


class SourceOut(BaseModel):
    id: str
    label: str
    status: str | None  # ok | error, None before the first collection


class StatusOut(BaseModel):
    last_run: RunOut | None
    last_success_at: datetime | None
    stale: bool  # no successful collection for more than 18 h
    llm_enabled: bool
    llm_cost_month_usd: float
    sources: list[SourceOut]


class ArticleOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    source: str
    link: str
    title: str
    summary: str
    published_at: datetime | None
    first_seen_at: datetime


class DigestOut(BaseModel):
    day: date
    text: str | None
    articles: list[ArticleOut]


def _utc(value: datetime | None) -> datetime | None:
    # SQLite does not keep timezone info: stored values are UTC.
    return value.replace(tzinfo=UTC) if value and value.tzinfo is None else value


def _out(article: Article) -> ArticleOut:
    out = ArticleOut.model_validate(article)
    out.published_at = _utc(out.published_at)
    out.first_seen_at = _utc(out.first_seen_at)
    return out


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
    last_digest = db.scalars(select(Digest).order_by(Digest.day.desc()).limit(1)).first()
    statuses = last_digest.sources if last_digest else {}
    last_success_at = _utc(last_ok.started_at) if last_ok else None
    return StatusOut(
        last_run=run_out,
        last_success_at=last_success_at,
        stale=last_success_at is None or datetime.now(UTC) - last_success_at > STALE_AFTER,
        llm_enabled=settings.anthropic_api_key is not None,
        llm_cost_month_usd=round(cost or 0.0, 4),
        sources=[SourceOut(id=f.id, label=f.label, status=statuses.get(f.id)) for f in FEEDS],
    )


@router.get("/digest/latest")
def latest_digest(db: DbSession) -> DigestOut | None:
    digest = db.scalars(select(Digest).order_by(Digest.day.desc()).limit(1)).first()
    if digest is None:
        return None
    articles = [_out(a) for a in day_articles(db, digest.article_ids)]
    return DigestOut(day=digest.day, text=digest.text, articles=articles)


@router.get("/articles")
def articles(
    db: DbSession,
    days: int = Query(default=7, ge=1, le=90),
    source: str | None = Query(default=None, max_length=50),
) -> list[ArticleOut]:
    """Articles first seen in the last `days` days, most recent first."""
    since = datetime.now(UTC) - timedelta(days=days)
    query = (
        select(Article)
        .where(Article.first_seen_at >= since)
        .order_by(func.coalesce(Article.published_at, Article.first_seen_at).desc(), Article.id)
        .limit(300)
    )
    if source is not None:
        query = query.where(Article.source == source)
    return [_out(a) for a in db.scalars(query)]
