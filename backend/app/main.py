"""FastAPI application factory."""

import logging

from fastapi import FastAPI

from app.auth.rate_limit import LoginRateLimiter
from app.auth.routes import router as auth_router
from app.config import Settings, get_settings
from app.db import make_engine, make_session_factory, run_migrations
from app.modules_registry import register_modules

logger = logging.getLogger(__name__)


def create_app(settings: Settings | None = None) -> FastAPI:
    settings = settings or get_settings()
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s")
    # httpx2 logs every URL at INFO, and some contain personal identifiers (OSINT).
    logging.getLogger("httpx2").setLevel(logging.WARNING)
    if settings.totp_secret is None:
        logger.warning("TOTP disabled: set JARVIS_TOTP_SECRET (python -m app.totp_setup)")

    # Interactive docs are disabled: the API is private and only used by the dashboard.
    app = FastAPI(title="Jarvis", docs_url=None, redoc_url=None, openapi_url=None)
    app.state.settings = settings
    engine = make_engine(settings.database_url)
    app.state.engine = engine
    app.state.session_factory = make_session_factory(engine)
    app.state.login_limiter = LoginRateLimiter()
    run_migrations(engine)

    app.include_router(auth_router)
    register_modules(app)

    @app.get("/api/health")
    def health() -> dict[str, str]:
        return {"status": "ok"}

    return app
