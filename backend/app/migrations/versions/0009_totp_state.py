"""TOTP replay protection: last accepted time step.

Revision ID: 0009
Revises: 0008
"""

import sqlalchemy as sa
from alembic import op

revision = "0009"
down_revision = "0008"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "totp_state",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("last_step", sa.Integer(), nullable=False),
    )


def downgrade() -> None:
    op.drop_table("totp_state")
