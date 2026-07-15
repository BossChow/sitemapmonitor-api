"""add site baseline state

Revision ID: 0004_add_site_baseline_state
Revises: 0003_add_site_check_lock
Create Date: 2026-07-14 00:00:00.000000
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "0004_add_site_baseline_state"
down_revision: str | None = "0003_add_site_check_lock"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "sites",
        sa.Column(
            "baseline_status",
            sa.String(length=32),
            nullable=False,
            server_default="completed",
        ),
    )
    op.add_column(
        "sites",
        sa.Column("baseline_started_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.add_column(
        "sites",
        sa.Column("baseline_completed_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.add_column(
        "sites",
        sa.Column("baseline_error_message", sa.Text(), nullable=True),
    )
    op.alter_column("sites", "baseline_status", server_default=None)


def downgrade() -> None:
    op.drop_column("sites", "baseline_error_message")
    op.drop_column("sites", "baseline_completed_at")
    op.drop_column("sites", "baseline_started_at")
    op.drop_column("sites", "baseline_status")
