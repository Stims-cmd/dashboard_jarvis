"""leboncoin analyses: no buyer criteria (they live in the Leboncoin search filters).

Revision ID: 0012
Revises: 0011
"""

import sqlalchemy as sa
from alembic import op

revision = "0012"
down_revision = "0011"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("lbc_analyses") as batch:
        batch.drop_column("criteria")


def downgrade() -> None:
    op.add_column(
        "lbc_analyses",
        sa.Column("criteria", sa.Text(), nullable=False, server_default=""),
    )
