"""FastAPI application factory."""

import logging

from fastapi import FastAPI

from app.auth import models as auth_models  # noqa: F401  (registers the table)
from app.auth.rate_limit import LoginRateLimiter
from app.auth.routes import router as auth_router
from app.config import Settings, get_settings
from app.db import Base, make_engine, make_session_factory
from app.modules_registry import register_modules


def create_app(settings: Settings | None = None) -> FastAPI:
    settings = settings or get_settings()
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s")

    # Interactive docs are disabled: the API is private and only used by the dashboard.
    app = FastAPI(title="Jarvis", docs_url=None, redoc_url=None, openapi_url=None)
    app.state.settings = settings
    engine = make_engine(settings.database_url)
    app.state.engine = engine
    app.state.session_factory = make_session_factory(engine)
    app.state.login_limiter = LoginRateLimiter()
    Base.metadata.create_all(engine)

    app.include_router(auth_router)
    register_modules(app)

    @app.get("/api/health")
    def health() -> dict[str, str]:
        return {"status": "ok"}

    return app
