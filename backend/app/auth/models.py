"""Server-side login sessions and TOTP replay state."""

from datetime import datetime

from sqlalchemy import DateTime, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base


class LoginSession(Base):
    __tablename__ = "sessions"

    # SHA-256 of the cookie token: a leaked database gives no usable token.
    token_hash: Mapped[str] = mapped_column(String(64), primary_key=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)


class TotpState(Base):
    """Single row: last accepted TOTP time step, to refuse replayed codes."""

    __tablename__ = "totp_state"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    last_step: Mapped[int] = mapped_column(Integer)
