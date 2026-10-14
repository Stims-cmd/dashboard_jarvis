from alembic import command
from alembic.autogenerate import compare_metadata
from alembic.config import Config
from alembic.migration import MigrationContext
from sqlalchemy import text

from app.db import MIGRATIONS_DIR, Base, import_all_models, make_engine, run_migrations


def test_migrations_match_models(tmp_path):
    """The migrations must create exactly the tables declared by the models."""
    engine = make_engine(f"sqlite:///{tmp_path / 'm.db'}")
    run_migrations(engine)
    import_all_models()
    with engine.connect() as connection:
        diff = compare_metadata(MigrationContext.configure(connection), Base.metadata)
    assert diff == []


def test_veille_news_migration_upgrades_old_digests(tmp_path):
    """0008 must work on a database that already holds CVE digests, and go back down."""
    engine = make_engine(f"sqlite:///{tmp_path / 'm.db'}")
    config = Config()
    config.set_main_option("script_location", str(MIGRATIONS_DIR))
    with engine.begin() as connection:
        config.attributes["connection"] = connection
        command.upgrade(config, "0007")
        connection.execute(
            text(
                "INSERT INTO vc_digests (day, cve_ids, text, created_at) "
                "VALUES ('2026-10-01', '[\"CVE-2026-0001\"]', NULL, '2026-10-01 06:30:00')"
            )
        )
        command.upgrade(config, "0008")
        assert connection.execute(text("SELECT count(*) FROM vc_digests")).scalar() == 0
        command.downgrade(config, "0007")
        command.upgrade(config, "head")


def test_migrations_can_run_twice(tmp_path):
    engine = make_engine(f"sqlite:///{tmp_path / 'm.db'}")
    run_migrations(engine)
    run_migrations(engine)
