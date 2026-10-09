"""Tables of the Finances module.

Amounts are integer cents and rates integer basis points (150 = 1.50 %): no float rounding.
No account number, IBAN or bank identifier is ever stored, only a label.
"""

from datetime import date, datetime

from sqlalchemy import Date, DateTime, ForeignKey, Integer, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base

ACCOUNT_KINDS = ("livret_a", "livret_jeune", "courant", "pro")
RATE_PRODUCTS = ("livret_a", "livret_jeune")


class Account(Base):
    __tablename__ = "fin_accounts"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    label: Mapped[str] = mapped_column(String(100))
    kind: Mapped[str] = mapped_column(String(20))
    ceiling_cents: Mapped[int | None] = mapped_column(Integer)
    closes_on: Mapped[date | None] = mapped_column(Date)  # e.g. end of the Livret Jeune
    position: Mapped[int] = mapped_column(Integer, default=0)


class Balance(Base):
    """Balance of an account on a given day, typed in by the owner."""

    __tablename__ = "fin_balances"
    __table_args__ = (UniqueConstraint("account_id", "day"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    account_id: Mapped[int] = mapped_column(ForeignKey("fin_accounts.id", ondelete="CASCADE"))
    day: Mapped[date] = mapped_column(Date)
    amount_cents: Mapped[int] = mapped_column(Integer)
    note: Mapped[str | None] = mapped_column(String(200))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class Rate(Base):
    """A rate checked by the owner at its source. Old rates are kept as history."""

    __tablename__ = "fin_rates"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    product: Mapped[str] = mapped_column(String(20), index=True)
    rate_bp: Mapped[int] = mapped_column(Integer)
    valid_from: Mapped[date] = mapped_column(Date)
    source_url: Mapped[str] = mapped_column(String(500))
    checked_on: Mapped[date] = mapped_column(Date)


class Goal(Base):
    __tablename__ = "fin_goals"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    label: Mapped[str] = mapped_column(String(100))
    target_cents: Mapped[int] = mapped_column(Integer)
    deadline: Mapped[date | None] = mapped_column(Date)
    # None: the goal covers all savings accounts (livrets).
    account_id: Mapped[int | None] = mapped_column(
        ForeignKey("fin_accounts.id", ondelete="SET NULL")
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
