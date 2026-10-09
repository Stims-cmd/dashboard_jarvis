"""Database engine, declarative base and migrations."""

import importlib
import pkgutil
from pathlib import Path

from alembic import command
from alembic.config import Config
from sqlalchemy import Engine, create_engine, event
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

MIGRATIONS_DIR = Path(__file__).parent / "migrations"


class Base(DeclarativeBase):
    pass


def make_engine(database_url: str) -> Engine:
    if database_url.startswith("sqlite:///"):
        db_path = database_url.removeprefix("sqlite:///")
        if db_path and db_path != ":memory:":
            Path(db_path).parent.mkdir(parents=True, exist_ok=True)
    # check_same_thread=False: FastAPI may use the connection from another thread.
    engine = create_engine(database_url, connect_args={"check_same_thread": False})
    if engine.dialect.name == "sqlite":
        # SQLite ignores foreign keys (and ON DELETE CASCADE) unless asked on each connection.
        event.listen(engine, "connect", _enable_sqlite_foreign_keys)
    return engine


def _enable_sqlite_foreign_keys(dbapi_connection, _record) -> None:
    cursor = dbapi_connection.cursor()
    cursor.execute("PRAGMA foreign_keys=ON")
    cursor.close()


def make_session_factory(engine: Engine) -> sessionmaker[Session]:
    return sessionmaker(bind=engine, expire_on_commit=False)


def import_all_models() -> None:
    """Import every file declaring tables, so that Base.metadata is complete."""
    import modules
    from app import core_models  # noqa: F401
    from app.auth import models  # noqa: F401

    for found in pkgutil.iter_modules(modules.__path__):
        name = f"modules.{found.name}.models"
        try:
            importlib.import_module(name)
        except ModuleNotFoundError as error:
            if error.name != name:  # a module without tables is fine, a broken import is not
                raise


def run_migrations(engine: Engine) -> None:
    """Bring the database schema up to date (same as "alembic upgrade head")."""
    config = Config()
    config.set_main_option("script_location", str(MIGRATIONS_DIR))
    with engine.begin() as connection:
        if engine.dialect.name == "sqlite":
            # Batch migrations recreate tables: with foreign keys on, dropping a parent
            # table would cascade-delete its children. Off for the migration only.
            connection.exec_driver_sql("PRAGMA foreign_keys=OFF")
        config.attributes["connection"] = connection
        command.upgrade(config, "head")
    # Drop pooled connections so the next ones are opened with foreign keys on again.
    engine.dispose()
