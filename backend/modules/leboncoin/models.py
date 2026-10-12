"""Tables of the Leboncoin module: ads read from alert emails, and processed emails.

Prices are integer cents. Only public ad data is stored, never the email content.
"""

from datetime import datetime

from sqlalchemy import JSON, DateTime, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base

MESSAGE_STATUSES = ("ok", "ignored", "parse_error")


class Ad(Base):
    __tablename__ = "lbc_ads"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    ad_id: Mapped[str] = mapped_column(String(30), unique=True)  # Leboncoin's own id
    search_name: Mapped[str] = mapped_column(String(200), index=True)  # first alert seen
    title: Mapped[str] = mapped_column(String(300))
    price_cents: Mapped[int | None] = mapped_column(Integer)  # None: no price shown
    location: Mapped[str] = mapped_column(String(200))
    url: Mapped[str] = mapped_column(String(500))
    # [[ISO datetime, price_cents], ...], one entry each time the price changes.
    price_history: Mapped[list] = mapped_column(JSON, default=list)
    first_seen_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    last_seen_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class Message(Base):
    """An alert email already handled, so it is never processed twice."""

    __tablename__ = "lbc_messages"

    key: Mapped[str] = mapped_column(String(64), primary_key=True)  # sha256 of Message-ID
    received_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    processed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    status: Mapped[str] = mapped_column(String(20))  # ok | ignored | parse_error
    ads_count: Mapped[int] = mapped_column(Integer, default=0)
