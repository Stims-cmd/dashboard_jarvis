"""Tables of the OSINT module. Subjects are labels or usernames, never raw emails/phones."""

from datetime import date, datetime

from sqlalchemy import JSON, Date, DateTime, Integer, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base

FINDING_KINDS = ("breach", "mention", "account", "gravatar")


class Finding(Base):
    __tablename__ = "osint_findings"
    __table_args__ = (UniqueConstraint("kind", "subject", "key"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    kind: Mapped[str] = mapped_column(String(20), index=True)
    subject: Mapped[str] = mapped_column(String(100))  # "email: perso", "name", "pseudo1"...
    source: Mapped[str] = mapped_column(String(50))
    key: Mapped[str] = mapped_column(String(500))  # breach name, URL or platform
    title: Mapped[str] = mapped_column(String(500))
    details: Mapped[dict] = mapped_column(JSON, default=dict)
    first_seen_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    last_seen_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class Report(Base):
    """Weekly report: what appeared since the previous one."""

    __tablename__ = "osint_reports"

    week: Mapped[date] = mapped_column(Date, primary_key=True)  # Monday of the ISO week
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    new_finding_ids: Mapped[list[int]] = mapped_column(JSON, default=list)
    sources: Mapped[dict] = mapped_column(JSON, default=dict)  # source -> ok | error | disabled
