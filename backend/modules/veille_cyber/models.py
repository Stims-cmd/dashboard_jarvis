"""Tables of the Veille cyber module."""

from datetime import date, datetime

from sqlalchemy import JSON, Boolean, Date, DateTime, Float, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base


class Vulnerability(Base):
    __tablename__ = "vc_vulnerabilities"

    cve_id: Mapped[str] = mapped_column(String(30), primary_key=True)
    vendor: Mapped[str | None] = mapped_column(String(200))
    product: Mapped[str | None] = mapped_column(String(200))
    title: Mapped[str | None] = mapped_column(String(500))
    description: Mapped[str] = mapped_column(Text, default="")
    published: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    cvss_score: Mapped[float | None] = mapped_column(Float)
    cvss_severity: Mapped[str | None] = mapped_column(String(20))
    cvss_version: Mapped[str | None] = mapped_column(String(10))
    epss: Mapped[float | None] = mapped_column(Float)
    epss_percentile: Mapped[float | None] = mapped_column(Float)
    in_kev: Mapped[bool] = mapped_column(Boolean, default=False)
    kev_date_added: Mapped[date | None] = mapped_column(Date, index=True)
    kev_due_date: Mapped[date | None] = mapped_column(Date)
    ransomware: Mapped[bool] = mapped_column(Boolean, default=False)
    first_seen_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class Digest(Base):
    """What was new on a given day, with the optional Claude summary."""

    __tablename__ = "vc_digests"

    day: Mapped[date] = mapped_column(Date, primary_key=True)
    cve_ids: Mapped[list[str]] = mapped_column(JSON, default=list)
    text: Mapped[str | None] = mapped_column(Text)  # None when Claude is not configured
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class ProductSheet(Base):
    """Short educational sheet about a product missing from skills.md."""

    __tablename__ = "vc_product_sheets"

    product_key: Mapped[str] = mapped_column(String(300), primary_key=True)
    vendor: Mapped[str | None] = mapped_column(String(200))
    product: Mapped[str] = mapped_column(String(200))
    text: Mapped[str] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
