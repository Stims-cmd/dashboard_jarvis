"""Ads collected from the alerts that look like a given item (sale help and ad analysis)."""

from sqlalchemy import select
from sqlalchemy.orm import Session

from modules.leboncoin.models import Ad

MAX_KEYWORDS = 5


def keywords(text: str) -> list[str]:
    """Lowercase words of 2 letters or more, at most MAX_KEYWORDS."""
    return [w for w in text.lower().split() if len(w) >= 2][:MAX_KEYWORDS]


def _like_escape(word: str) -> str:
    """The word is matched literally: % and _ are not wildcards."""
    return word.replace("\\", "\\\\").replace("%", "\%").replace("_", "\_")


def find_comparables(db: Session, words: list[str]) -> list[Ad]:
    """Collected ads whose title contains every word, newest first."""
    if not words:
        return []
    query = select(Ad)
    # Parameterized LIKE. SQLite ignores case for ASCII letters only: "VÉLO" != "vélo".
    for word in words:
        query = query.where(Ad.title.ilike(f"%{_like_escape(word)}%", escape="\\"))
    return list(db.scalars(query.order_by(Ad.first_seen_at.desc())).all())
