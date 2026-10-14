"""Collection of cyber news (CERT-FR, press), twice a day, then summarized by Claude."""

import logging
from collections.abc import Sequence
from datetime import date, datetime, timedelta

from sqlalchemy import select

from app.collect import CollectContext
from modules.veille_cyber.digest import DIGEST_SYSTEM, digest_prompt
from modules.veille_cyber.models import Article, Digest
from modules.veille_cyber.sources.feeds import FEEDS, Feed, RawArticle, fetch_feed, parse_feed

logger = logging.getLogger(__name__)

# First run: older articles are stored as history, only these count as "new".
FIRST_RUN_WINDOW = timedelta(hours=48)


def collect(ctx: CollectContext, feeds: Sequence[Feed] = FEEDS) -> dict[str, int]:
    first_run = ctx.last_success_at is None
    statuses: dict[str, str] = {}
    new_ids: list[int] = []
    for feed in feeds:
        try:
            raw = parse_feed(fetch_feed(ctx.http, feed.url))
        except Exception as error:  # noqa: BLE001 - one broken feed must not stop the others
            logger.warning("veille_cyber: feed %s failed: %s", feed.id, type(error).__name__)
            statuses[feed.id] = "error"
            continue
        statuses[feed.id] = "ok"
        new_ids += _store(ctx, feed.id, raw, first_run)

    articles = _update_digest(ctx, ctx.now.date(), new_ids, statuses)
    summarized = _summarize(ctx, ctx.now.date(), articles)
    errors = sum(1 for s in statuses.values() if s == "error")
    if errors == len(feeds):
        # Nothing could be read: the run is a failure, visible in the window and in systemd.
        raise RuntimeError("every feed failed")
    return {"new_articles": len(new_ids), "feed_errors": errors, "digest": int(summarized)}


def _store(ctx: CollectContext, source: str, raw: list[RawArticle], first_run: bool) -> list[int]:
    """Insert unknown articles; return the ids of those counting as new today."""
    new_ids = []
    for item in raw:
        if ctx.db.scalar(select(Article.id).where(Article.link == item.link)) is not None:
            continue
        article = Article(
            source=source,
            link=item.link,
            title=item.title,
            summary=item.summary,
            published_at=item.published_at,
            first_seen_at=ctx.now,
        )
        ctx.db.add(article)
        ctx.db.flush()  # assigns the id
        recent = item.published_at is None or ctx.now - item.published_at <= FIRST_RUN_WINDOW
        if not first_run or recent:
            new_ids.append(article.id)
    ctx.db.commit()
    return new_ids


def _update_digest(
    ctx: CollectContext, day: date, new_ids: list[int], statuses: dict[str, str]
) -> list[Article]:
    """Add this run's articles to the day's digest; return all of the day's articles."""
    digest = ctx.db.get(Digest, day) or Digest(day=day, article_ids=[], created_at=ctx.now)
    # Several runs on the same day add up instead of replacing each other.
    digest.article_ids = list(dict.fromkeys(digest.article_ids + new_ids))
    digest.sources = statuses
    digest.created_at = ctx.now
    ctx.db.add(digest)
    ctx.db.commit()
    return day_articles(ctx.db, digest.article_ids)


def day_articles(db, article_ids: list[int]) -> list[Article]:
    """Articles of a digest, most recent first."""
    if not article_ids:
        return []
    found = db.scalars(select(Article).where(Article.id.in_(article_ids)))
    oldest = datetime.min
    return sorted(
        found, key=lambda a: (a.published_at or oldest).replace(tzinfo=None), reverse=True
    )


def _summarize(ctx: CollectContext, day: date, articles: list[Article]) -> bool:
    if not articles or not ctx.llm.enabled:
        return False
    text = ctx.llm.complete("veille_cyber.digest", DIGEST_SYSTEM, digest_prompt(articles))
    if text:
        ctx.db.get(Digest, day).text = text
        ctx.db.commit()
    return text is not None
