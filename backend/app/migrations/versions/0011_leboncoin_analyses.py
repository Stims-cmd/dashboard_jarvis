"""leboncoin analyses

Revision ID: 0011
Revises: 0010
"""

import sqlalchemy as sa
from alembic import op

revision = "0011"
down_revision = "0010"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "lbc_analyses",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("title", sa.String(length=200), nullable=False),
        sa.Column("ad_text", sa.Text(), nullable=False),
        sa.Column("criteria", sa.Text(), nullable=False),
        sa.Column("keywords", sa.String(length=200), nullable=False),
        sa.Column("price_cents", sa.Integer(), nullable=True),
        sa.Column("signals", sa.JSON(), nullable=False),
        sa.Column("comparables", sa.JSON(), nullable=False),
        sa.Column("result", sa.JSON(), nullable=True),
        sa.Column("sources", sa.JSON(), nullable=False),
        sa.Column("source", sa.String(length=20), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    with op.batch_alter_table("lbc_analyses", schema=None) as batch_op:
        batch_op.create_index(
            batch_op.f("ix_lbc_analyses_created_at"), ["created_at"], unique=False
        )


def downgrade() -> None:
    with op.batch_alter_table("lbc_analyses", schema=None) as batch_op:
        batch_op.drop_index(batch_op.f("ix_lbc_analyses_created_at"))
    op.drop_table("lbc_analyses")
