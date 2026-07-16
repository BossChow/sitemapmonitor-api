"""add sitemap URL parsed lastmod timestamp

Revision ID: 0008_add_sitemap_url_lastmod_at
Revises: 0007_add_frontend_auth_tables
Create Date: 2026-07-16 00:00:00.000000
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "0008_add_sitemap_url_lastmod_at"
down_revision: str | None = "0007_add_frontend_auth_tables"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "sitemap_urls",
        sa.Column("lastmod_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.execute(
        """
        UPDATE sitemap_urls
        SET lastmod_at = lastmod::timestamptz
        WHERE lastmod ~ '^\\d{4}-\\d{2}-\\d{2}($|T| )'
        """
    )
    op.create_index(
        "ix_sitemap_urls_site_id_removed_at_lastmod_at",
        "sitemap_urls",
        ["site_id", "removed_at", "lastmod_at"],
    )
    op.create_index(
        "ix_sitemap_urls_site_id_removed_at_first_seen_at",
        "sitemap_urls",
        ["site_id", "removed_at", "first_seen_at"],
    )


def downgrade() -> None:
    op.drop_index("ix_sitemap_urls_site_id_removed_at_first_seen_at", table_name="sitemap_urls")
    op.drop_index("ix_sitemap_urls_site_id_removed_at_lastmod_at", table_name="sitemap_urls")
    op.drop_column("sitemap_urls", "lastmod_at")
