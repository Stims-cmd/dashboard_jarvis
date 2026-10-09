"""Dependency protecting routes behind a valid login session."""

from datetime import UTC, datetime
from typing import Annotated

from fastapi import Cookie, Depends, HTTPException, status
from sqlalchemy import select

from app.auth.models import LoginSession
from app.auth.security import hash_token
from app.deps import AppSettings, DbSession

SESSION_COOKIE = "jarvis_session"


def require_user(
    db: DbSession,
    settings: AppSettings,
    jarvis_session: Annotated[str | None, Cookie()] = None,
) -> str:
    if jarvis_session:
        session = db.scalar(
            select(LoginSession).where(LoginSession.token_hash == hash_token(jarvis_session))
        )
        if session and _as_utc(session.expires_at) > datetime.now(UTC):
            return settings.admin_username
    raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Not authenticated")


def _as_utc(value: datetime) -> datetime:
    # SQLite does not keep timezone info: stored values are UTC.
    return value if value.tzinfo else value.replace(tzinfo=UTC)


CurrentUser = Annotated[str, Depends(require_user)]
