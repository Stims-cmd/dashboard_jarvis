"""API of the ad analysis, under /api/modules/leboncoin/analyses.

The owner pastes an ad: Jarvis never fetches leboncoin.fr. Contact details are removed
before storage and before anything is sent to Claude. Logs record ids only, never texts.
"""

import logging
from datetime import UTC, datetime
from typing import Literal

from fastapi import APIRouter, HTTPException, Response, status
from pydantic import BaseModel, Field, ValidationError
from sqlalchemy import select

from app.deps import DbSession
from modules.leboncoin import analysis
from modules.leboncoin.analysis import AnalysisResult
from modules.leboncoin.comparables import find_comparables, keywords
from modules.leboncoin.models import AdAnalysis
from modules.leboncoin.sales import comparables_stats, redact
from modules.leboncoin.sales_routes import Llm

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/analyses")

HISTORY_SHOWN = 20
MAX_SOURCES = 10
MAX_SEARCHES = 5


class AnalysisIn(BaseModel):
    text: str = Field(min_length=1, max_length=analysis.MAX_AD_CHARS)
    keywords: str = Field(default="", max_length=200)  # empty: taken from the title


class StatsOut(BaseModel):
    count: int = 0
    min_cents: int | None = None
    median_cents: int | None = None
    max_cents: int | None = None


class SourceOut(BaseModel):
    url: str
    title: str


class AnalysisOut(BaseModel):
    id: int
    title: str
    ad_text: str
    keywords: str
    price_cents: int | None
    signals: list[str]
    comparables: StatsOut
    result: AnalysisResult | None
    # (min, max) cents: price + registration fees + repairs, vehicles only.
    estimated_total_cents: tuple[int, int] | None
    sources: list[SourceOut]
    source: Literal["claude", "local"]
    created_at: datetime


def _result(row: AdAnalysis) -> AnalysisResult | None:
    """Analyses stored in an older format are shown without Claude's part."""
    if row.result is None:
        return None
    try:
        return AnalysisResult.model_validate(row.result)
    except ValidationError:
        return None


def _out(row: AdAnalysis) -> AnalysisOut:
    created = row.created_at
    result = _result(row)
    return AnalysisOut(
        id=row.id,
        title=row.title,
        ad_text=row.ad_text,
        keywords=row.keywords,
        price_cents=row.price_cents,
        signals=row.signals,
        comparables=StatsOut(**row.comparables),
        result=result,
        estimated_total_cents=analysis.estimated_total(
            row.price_cents, result.vehicule if result else None
        ),
        sources=row.sources if result else [],
        source=row.source,
        created_at=created.replace(tzinfo=UTC) if created.tzinfo is None else created,
    )


def _get_or_404(db: DbSession, analysis_id: int) -> AdAnalysis:
    row = db.get(AdAnalysis, analysis_id)
    if row is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND)
    return row


@router.get("")
def list_analyses(db: DbSession) -> list[AnalysisOut]:
    query = select(AdAnalysis).order_by(AdAnalysis.id.desc()).limit(HISTORY_SHOWN)
    return [_out(row) for row in db.scalars(query)]


@router.get("/{analysis_id}")
def get_analysis(analysis_id: int, db: DbSession) -> AnalysisOut:
    return _out(_get_or_404(db, analysis_id))


@router.post("", status_code=status.HTTP_201_CREATED)
def create_analysis(data: AnalysisIn, db: DbSession, llm: Llm) -> AnalysisOut:
    """Analyses a pasted ad. Can take up to a minute when Claude searches the web."""
    title = analysis.ad_title(data.text)
    price = analysis.guess_price_cents(data.text)
    words = keywords(data.keywords or analysis.title_keywords(title))
    found = find_comparables(db, words)
    stats = comparables_stats([a.price_cents for a in found if a.price_cents is not None])
    # Signals are searched in the raw text: contact details are one of them.
    signals = analysis.scam_signals(data.text, price, stats)
    ad_text = redact(data.text)

    result, sources = None, []
    if llm.enabled:
        research = llm.research(
            "leboncoin.analysis",
            analysis.SYSTEM,
            analysis.analysis_prompt(ad_text, price, stats, signals),
            max_searches=MAX_SEARCHES,
            blocked_domains=["leboncoin.fr"],
        )
        if research is not None:
            result = analysis.parse_analysis(research.text)
            # Web pages are untrusted: only https links reach the page.
            sources = [
                {"url": s.url, "title": s.title[:200]}
                for s in research.sources
                if s.url.startswith("https://")
            ][:MAX_SOURCES]

    row = AdAnalysis(
        title=redact(title) or "Annonce sans titre",
        ad_text=ad_text,
        keywords=" ".join(words),
        price_cents=price,
        signals=signals,
        comparables=stats.__dict__,
        result=result.model_dump() if result else None,
        sources=sources if result else [],
        source="claude" if result else "local",
        created_at=datetime.now(UTC),
    )
    db.add(row)
    db.commit()
    logger.info("leboncoin: analysis %d (%s)", row.id, row.source)
    return _out(row)


@router.delete("/{analysis_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_analysis(analysis_id: int, db: DbSession) -> Response:
    db.delete(_get_or_404(db, analysis_id))
    db.commit()
    logger.info("leboncoin: analysis %d deleted", analysis_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)
