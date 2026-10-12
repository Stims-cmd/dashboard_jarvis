"""Tables of the Leboncoin module: ads read from alert emails, processed emails,
and the owner's own items for sale.

Prices are integer cents. Only public ad data is stored, never the email content.
"""

from datetime import date, datetime

from sqlalchemy import JSON, Date, DateTime, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base

MESSAGE_STATUSES = ("ok", "ignored", "parse_error")
ITEM_CONDITIONS = ("neuf", "tres_bon", "bon", "correct", "pieces")
ITEM_STATUSES = ("draft", "listed", "sold", "withdrawn")


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


class Item(Base):
    """Something the owner sells. Jarvis only prepares texts: the owner publishes."""

    __tablename__ = "lbc_items"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    title: Mapped[str] = mapped_column(String(100))
    condition: Mapped[str] = mapped_column(String(20))  # see ITEM_CONDITIONS
    notes: Mapped[str] = mapped_column(Text, default="")  # defects, accessories, sizes...
    keywords: Mapped[str] = mapped_column(String(200), default="")  # to find comparable ads
    asking_price_cents: Mapped[int] = mapped_column(Integer)
    floor_price_cents: Mapped[int | None] = mapped_column(Integer)  # lowest acceptable price
    status: Mapped[str] = mapped_column(String(20), default="draft")  # see ITEM_STATUSES
    listed_on: Mapped[date | None] = mapped_column(Date)
    lower_after_days: Mapped[int] = mapped_column(Integer, default=14)
    # [[ISO date, price_cents], ...], one entry each time the asking price changes.
    price_history: Mapped[list] = mapped_column(JSON, default=list)
    draft_title: Mapped[str | None] = mapped_column(String(100))
    draft_body: Mapped[str | None] = mapped_column(Text)
    draft_source: Mapped[str | None] = mapped_column(String(20))  # claude | template
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
