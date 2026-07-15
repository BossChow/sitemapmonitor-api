"""make sitemap URL optional

Revision ID: 0006_make_sitemap_url_optional
Revises: 0005_merge_site_status
Create Date: 2026-07-15 00:00:00.000000
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "0006_make_sitemap_url_optional"
down_revision: str | None = "0005_merge_site_status"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.alter_column("sites", "sitemap_url", existing_type=sa.Text(), nullable=True)


def downgrade() -> None:
    op.execute("UPDATE sites SET sitemap_url = root_url WHERE sitemap_url IS NULL")
    op.alter_column("sites", "sitemap_url", existing_type=sa.Text(), nullable=False)
