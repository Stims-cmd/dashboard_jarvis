"""Collector runs and Claude API usage log.

Revision ID: 0002
Revises: 0001
"""

import sqlalchemy as sa
from alembic import op

revision = "0002"
down_revision = "0001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "collector_runs",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("module", sa.String(50), nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("finished_at", sa.DateTime(timezone=True)),
        sa.Column("status", sa.String(20), nullable=False),
        sa.Column("summary", sa.String(500)),
    )
    op.create_index("ix_collector_runs_module", "collector_runs", ["module"])
    op.create_table(
        "llm_calls",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("purpose", sa.String(100), nullable=False),
        sa.Column("model", sa.String(100), nullable=False),
        sa.Column("input_tokens", sa.Integer, nullable=False),
        sa.Column("output_tokens", sa.Integer, nullable=False),
        sa.Column("stop_reason", sa.String(30)),
        sa.Column("cost_usd", sa.Float),
    )
    op.create_index("ix_llm_calls_created_at", "llm_calls", ["created_at"])


def downgrade() -> None:
    op.drop_table("llm_calls")
    op.drop_table("collector_runs")
