"""Login (password + optional TOTP code), logout and current-user routes."""

import logging
from datetime import UTC, datetime, timedelta

from fastapi import APIRouter, Cookie, HTTPException, Request, Response, status
from pydantic import BaseModel, Field
from sqlalchemy import delete

from app.auth.deps import SESSION_COOKIE, CurrentUser
from app.auth.models import LoginSession, TotpState
from app.auth.security import check_credentials, hash_token, new_session_token
from app.auth.totp import verify_code
from app.deps import AppSettings, DbSession

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/auth", tags=["auth"])


class LoginRequest(BaseModel):
    username: str = Field(max_length=200)
    password: str = Field(max_length=200)
    # 6-digit TOTP code, required only when JARVIS_TOTP_SECRET is set.
    code: str = Field(default="", max_length=10)


class UserResponse(BaseModel):
    username: str


class AuthConfigResponse(BaseModel):
    totp: bool


@router.get("/config")
def auth_config(settings: AppSettings) -> AuthConfigResponse:
    """Public: tells the login page whether to ask for a TOTP code."""
    return AuthConfigResponse(totp=settings.totp_secret is not None)


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

    password_ok = check_credentials(
        body.username, body.password, settings.admin_username, settings.password_hash
    )
    totp_ok = True
    totp_state = None
    if settings.totp_secret is not None:
        # Checked even when the password is wrong: the response time and the
        # error message never tell which factor failed.
        totp_state = db.get(TotpState, 1)
        step = verify_code(
            settings.totp_secret.get_secret_value(),
            body.code,
            totp_state.last_step if totp_state else None,
        )
        totp_ok = step is not None
    if not (password_ok and totp_ok):
        limiter.record_failure(client_ip)
        logger.info("login failed")
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Invalid credentials")

    limiter.reset(client_ip)
    if settings.totp_secret is not None:
        if totp_state is None:
            db.add(TotpState(id=1, last_step=step))
        else:
            totp_state.last_step = step
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
