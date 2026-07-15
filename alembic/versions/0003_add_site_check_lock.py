"""add site check lock

Revision ID: 0003_add_site_check_lock
Revises: 0002_add_tracked_change_types
Create Date: 2026-07-14 00:00:00.000000
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "0003_add_site_check_lock"
down_revision: str | None = "0002_add_tracked_change_types"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "sites",
        sa.Column("checking_started_at", sa.DateTime(timezone=True), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("sites", "checking_started_at")
