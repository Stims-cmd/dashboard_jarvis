from alembic.autogenerate import compare_metadata
from alembic.migration import MigrationContext

from app.db import Base, import_all_models, make_engine, run_migrations


def test_migrations_match_models(tmp_path):
    """The migrations must create exactly the tables declared by the models."""
    engine = make_engine(f"sqlite:///{tmp_path / 'm.db'}")
    run_migrations(engine)
    import_all_models()
    with engine.connect() as connection:
        diff = compare_metadata(MigrationContext.configure(connection), Base.metadata)
    assert diff == []


def test_migrations_can_run_twice(tmp_path):
    engine = make_engine(f"sqlite:///{tmp_path / 'm.db'}")
    run_migrations(engine)
    run_migrations(engine)
