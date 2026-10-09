"""Login, logout and current-user routes."""

import logging
from datetime import UTC, datetime, timedelta

from fastapi import APIRouter, Cookie, HTTPException, Request, Response, status
from pydantic import BaseModel, Field
from sqlalchemy import delete

from app.auth.deps import SESSION_COOKIE, CurrentUser
from app.auth.models import LoginSession
from app.auth.security import check_credentials, hash_token, new_session_token
from app.deps import AppSettings, DbSession

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/auth", tags=["auth"])


class LoginRequest(BaseModel):
    username: str = Field(max_length=200)
    password: str = Field(max_length=200)


class UserResponse(BaseModel):
    username: str


@router.post("/login", status_code=status.HTTP_204_NO_CONTENT)
def login(
    body: LoginRequest,
    request: Request,
    response: Response,
    db: DbSession,
    settings: AppSettings,
) -> None:
    limiter = request.app.state.login_limiter
    client_ip = request.client.host if request.client else "unknown"
    if limiter.is_blocked(client_ip):
        logger.warning("login blocked: too many failures")
        raise HTTPException(status.HTTP_429_TOO_MANY_REQUESTS, "Too many attempts, retry later")

    if not check_credentials(
        body.username, body.password, settings.admin_username, settings.password_hash
    ):
        limiter.record_failure(client_ip)
        logger.info("login failed")
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Invalid credentials")

    limiter.reset(client_ip)
    now = datetime.now(UTC)
    token = new_session_token()
    db.execute(delete(LoginSession).where(LoginSession.expires_at <= now))
    db.add(
        LoginSession(
            token_hash=hash_token(token),
            created_at=now,
            expires_at=now + timedelta(hours=settings.session_hours),
        )
    )
    db.commit()
    response.set_cookie(
        SESSION_COOKIE,
        token,
        max_age=settings.session_hours * 3600,
        httponly=True,
        secure=settings.cookie_secure,
        samesite="strict",
        path="/",
    )
    logger.info("login ok")


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
def logout(
    response: Response,
    db: DbSession,
    jarvis_session: str | None = Cookie(default=None),
) -> None:
    if jarvis_session:
        db.execute(
            delete(LoginSession).where(LoginSession.token_hash == hash_token(jarvis_session))
        )
        db.commit()
    response.delete_cookie(SESSION_COOKIE, path="/")


@router.get("/me")
def me(user: CurrentUser) -> UserResponse:
    return UserResponse(username=user)
