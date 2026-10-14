"""veille cyber news: articles from public feeds replace CVE tracking

Revision ID: 0008
Revises: 0007

The CVE tables and the old CVE digests are dropped (their content is not news).
"""

import sqlalchemy as sa
from alembic import op

revision = "0008"
down_revision = "0007"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("vc_product_sheets", schema=None) as batch_op:
        batch_op.drop_index(batch_op.f("ix_vc_product_sheets_created_at"))
    op.drop_table("vc_product_sheets")
    with op.batch_alter_table("vc_vulnerabilities", schema=None) as batch_op:
        batch_op.drop_index(batch_op.f("ix_vc_vulnerabilities_kev_date_added"))
    op.drop_table("vc_vulnerabilities")
    op.drop_table("vc_digests")

    op.create_table(
        "vc_articles",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("source", sa.String(length=50), nullable=False),
        sa.Column("link", sa.String(length=500), nullable=False),
        sa.Column("title", sa.String(length=300), nullable=False),
        sa.Column("summary", sa.Text(), nullable=False),
        sa.Column("published_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("first_seen_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("link"),
    )
    with op.batch_alter_table("vc_articles", schema=None) as batch_op:
        batch_op.create_index(
            batch_op.f("ix_vc_articles_first_seen_at"), ["first_seen_at"], unique=False
        )
        batch_op.create_index(
            batch_op.f("ix_vc_articles_published_at"), ["published_at"], unique=False
        )
        batch_op.create_index(batch_op.f("ix_vc_articles_source"), ["source"], unique=False)

    op.create_table(
        "vc_digests",
        sa.Column("day", sa.Date(), nullable=False),
        sa.Column("article_ids", sa.JSON(), nullable=False),
        sa.Column("sources", sa.JSON(), nullable=False),
        sa.Column("text", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("day"),
    )


def downgrade() -> None:
    # Back to the CVE schema of revision 0003 (empty tables: news are not converted).
    op.drop_table("vc_digests")
    with op.batch_alter_table("vc_articles", schema=None) as batch_op:
        batch_op.drop_index(batch_op.f("ix_vc_articles_source"))
        batch_op.drop_index(batch_op.f("ix_vc_articles_published_at"))
        batch_op.drop_index(batch_op.f("ix_vc_articles_first_seen_at"))
    op.drop_table("vc_articles")

    op.create_table(
        "vc_digests",
        sa.Column("day", sa.Date(), nullable=False),
        sa.Column("cve_ids", sa.JSON(), nullable=False),
        sa.Column("text", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("day"),
    )
    op.create_table(
        "vc_product_sheets",
        sa.Column("product_key", sa.String(length=300), nullable=False),
        sa.Column("vendor", sa.String(length=200), nullable=True),
        sa.Column("product", sa.String(length=200), nullable=False),
        sa.Column("text", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("product_key"),
    )
    with op.batch_alter_table("vc_product_sheets", schema=None) as batch_op:
        batch_op.create_index(
            batch_op.f("ix_vc_product_sheets_created_at"), ["created_at"], unique=False
        )
    op.create_table(
        "vc_vulnerabilities",
        sa.Column("cve_id", sa.String(length=30), nullable=False),
        sa.Column("vendor", sa.String(length=200), nullable=True),
        sa.Column("product", sa.String(length=200), nullable=True),
        sa.Column("title", sa.String(length=500), nullable=True),
        sa.Column("description", sa.Text(), nullable=False),
        sa.Column("published", sa.DateTime(timezone=True), nullable=True),
        sa.Column("cvss_score", sa.Float(), nullable=True),
        sa.Column("cvss_severity", sa.String(length=20), nullable=True),
        sa.Column("cvss_version", sa.String(length=10), nullable=True),
        sa.Column("epss", sa.Float(), nullable=True),
        sa.Column("epss_percentile", sa.Float(), nullable=True),
        sa.Column("in_kev", sa.Boolean(), nullable=False),
        sa.Column("kev_date_added", sa.Date(), nullable=True),
        sa.Column("kev_due_date", sa.Date(), nullable=True),
        sa.Column("ransomware", sa.Boolean(), nullable=False),
        sa.Column("first_seen_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("cve_id"),
    )
    with op.batch_alter_table("vc_vulnerabilities", schema=None) as batch_op:
        batch_op.create_index(
            batch_op.f("ix_vc_vulnerabilities_kev_date_added"), ["kev_date_added"], unique=False
        )
