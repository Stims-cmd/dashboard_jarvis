"""Alembic environment.

From the app, run_migrations() passes its connection. From the CLI
(e.g. "alembic revision --autogenerate -m ..."), the URL comes from the settings.
"""

from alembic import context
from sqlalchemy import Connection, create_engine

from app.db import Base, import_all_models

import_all_models()
target_metadata = Base.metadata


def _migrate(connection: Connection) -> None:
    # render_as_batch: SQLite cannot ALTER most things, Alembic recreates the table instead.
    context.configure(connection=connection, target_metadata=target_metadata, render_as_batch=True)
    with context.begin_transaction():
        context.run_migrations()


def run() -> None:
    connection = context.config.attributes.get("connection")
    if connection is not None:
        _migrate(connection)
        return

    from app.config import get_settings

    with create_engine(get_settings().database_url).connect() as cli_connection:
        _migrate(cli_connection)
        cli_connection.commit()


run()
