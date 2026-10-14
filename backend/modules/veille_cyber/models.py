"""Tables of the Veille cyber module: news articles and the daily digest."""

from datetime import date, datetime

from sqlalchemy import JSON, Date, DateTime, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base


class Article(Base):
    """A news item read from a public feed (CERT-FR, press). Public data only."""

    __tablename__ = "vc_articles"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    source: Mapped[str] = mapped_column(String(50), index=True)  # Feed.id
    link: Mapped[str] = mapped_column(String(500), unique=True)
    title: Mapped[str] = mapped_column(String(300))
    summary: Mapped[str] = mapped_column(Text, default="")
    published_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), index=True)
    first_seen_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)


class Digest(Base):
    """What was new on a given day, with the optional Claude summary."""

    __tablename__ = "vc_digests"

    day: Mapped[date] = mapped_column(Date, primary_key=True)
    article_ids: Mapped[list[int]] = mapped_column(JSON, default=list)
    sources: Mapped[dict] = mapped_column(JSON, default=dict)  # feed id -> ok | error
    text: Mapped[str | None] = mapped_column(Text)  # None when Claude is not configured
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
