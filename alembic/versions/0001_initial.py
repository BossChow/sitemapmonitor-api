"""initial schema

Revision ID: 0001_initial
Revises:
Create Date: 2026-07-12 00:00:00.000000
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "0001_initial"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "sites",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("owner_user_id", sa.String(length=128), nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("root_url", sa.Text(), nullable=False),
        sa.Column("sitemap_url", sa.Text(), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False, server_default="active"),
        sa.Column("check_frequency", sa.String(length=32), nullable=False, server_default="daily"),
        sa.Column("last_checked_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("next_check_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_sites_owner_user_id", "sites", ["owner_user_id"])
    op.create_index("ix_sites_next_check_at", "sites", ["next_check_at"])
    op.create_index("ix_sites_status_next_check_at", "sites", ["status", "next_check_at"])

    op.create_table(
        "sitemap_checks",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("owner_user_id", sa.String(length=128), nullable=False),
        sa.Column(
            "site_id",
            sa.Integer(),
            sa.ForeignKey("sites.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("url_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("added_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("removed_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("updated_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("error_message", sa.Text(), nullable=True),
    )
    op.create_index("ix_sitemap_checks_owner_user_id", "sitemap_checks", ["owner_user_id"])
    op.create_index(
        "ix_sitemap_checks_site_id_started_at",
        "sitemap_checks",
        ["site_id", "started_at"],
    )

    op.create_table(
        "sitemap_urls",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "site_id",
            sa.Integer(),
            sa.ForeignKey("sites.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("url_hash", sa.String(length=64), nullable=False),
        sa.Column("url", sa.Text(), nullable=False),
        sa.Column("lastmod", sa.String(length=64), nullable=True),
        sa.Column("first_seen_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("last_seen_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column(
            "last_seen_check_id",
            sa.Integer(),
            sa.ForeignKey("sitemap_checks.id"),
            nullable=True,
        ),
        sa.Column("removed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("site_id", "url_hash", name="uq_sitemap_urls_site_id_url_hash"),
    )
    op.create_index("ix_sitemap_urls_site_id_removed_at", "sitemap_urls", ["site_id", "removed_at"])

    op.create_table(
        "sitemap_url_changes",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("owner_user_id", sa.String(length=128), nullable=False),
        sa.Column(
            "site_id",
            sa.Integer(),
            sa.ForeignKey("sites.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "check_id",
            sa.Integer(),
            sa.ForeignKey("sitemap_checks.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "url_id",
            sa.Integer(),
            sa.ForeignKey("sitemap_urls.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("change_type", sa.String(length=32), nullable=False),
        sa.Column("url", sa.Text(), nullable=False),
        sa.Column("old_lastmod", sa.String(length=64), nullable=True),
        sa.Column("new_lastmod", sa.String(length=64), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index(
        "ix_sitemap_url_changes_owner_user_id",
        "sitemap_url_changes",
        ["owner_user_id"],
    )
    op.create_index(
        "ix_sitemap_url_changes_site_id_created_at",
        "sitemap_url_changes",
        ["site_id", "created_at"],
    )


def downgrade() -> None:
    op.drop_table("sitemap_url_changes")
    op.drop_table("sitemap_urls")
    op.drop_table("sitemap_checks")
    op.drop_table("sites")
