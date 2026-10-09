"""Run a module's collector: python -m app.collect <module_id>

Launched by the scheduler (systemd timer on the server) or by hand in development.
A module takes part by defining collect(ctx: CollectContext) -> dict[str, int]
in its __init__.py.
"""

import importlib
import logging
import sys
from dataclasses import dataclass
from datetime import UTC, datetime

import httpx2
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import Settings, get_settings
from app.core_models import CollectorRun
from app.db import make_engine, make_session_factory, run_migrations
from app.http import make_http_client
from app.llm import LlmClient

logger = logging.getLogger(__name__)


@dataclass
class CollectContext:
    db: Session
    http: httpx2.Client
    llm: LlmClient
    settings: Settings
    now: datetime
    last_success_at: datetime | None  # start of the previous successful run


def last_success(db: Session, module_id: str) -> datetime | None:
    started = db.scalar(
        select(CollectorRun.started_at)
        .where(CollectorRun.module == module_id, CollectorRun.status == "ok")
        .order_by(CollectorRun.started_at.desc())
        .limit(1)
    )
    # SQLite does not keep timezone info: stored values are UTC.
    return started.replace(tzinfo=UTC) if started and started.tzinfo is None else started


def run_collector(
    module_id: str, db: Session, settings: Settings, http: httpx2.Client, llm: LlmClient
) -> CollectorRun:
    collect = getattr(importlib.import_module(f"modules.{module_id}"), "collect", None)
    if collect is None:
        raise SystemExit(f"Module {module_id!r} has no collector.")

    now = datetime.now(UTC)
    ctx = CollectContext(db, http, llm, settings, now, last_success(db, module_id))
    run = CollectorRun(module=module_id, started_at=now, status="running")
    db.add(run)
    db.commit()
    try:
        counts = collect(ctx)
        run.status = "ok"
        run.summary = ", ".join(f"{key}={value}" for key, value in counts.items())
    except Exception as error:
        db.rollback()
        run.status = "error"
        run.summary = f"{type(error).__name__}: {error}"[:500]
        logger.exception("collector %s failed", module_id)
    run.finished_at = datetime.now(UTC)
    db.add(run)
    db.commit()
    return run


def main(argv: list[str]) -> int:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s")
    if len(argv) != 2:
        print("Usage: python -m app.collect <module_id>", file=sys.stderr)
        return 2
    settings = get_settings()
    engine = make_engine(settings.database_url)
    run_migrations(engine)
    with make_session_factory(engine)() as db, make_http_client() as http:
        run = run_collector(argv[1], db, settings, http, LlmClient(settings, db))
    logger.info("collector %s: %s (%s)", argv[1], run.status, run.summary)
    # A non-zero exit code makes the failure visible in systemctl / journalctl.
    return 0 if run.status == "ok" else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv))
