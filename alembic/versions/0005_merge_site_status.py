"""merge site status

Revision ID: 0005_merge_site_status
Revises: 0004_add_site_baseline_state
Create Date: 2026-07-14 00:00:00.000000
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "0005_merge_site_status"
down_revision: str | None = "0004_add_site_baseline_state"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute(
        """
        UPDATE sites
        SET status = CASE
            WHEN baseline_status IN ('pending', 'running') THEN 'initializing'
            WHEN baseline_status = 'failed' THEN 'failed'
            ELSE status
        END
        """
    )
    op.drop_column("sites", "baseline_status")


def downgrade() -> None:
    op.add_column(
        "sites",
        sa.Column(
            "baseline_status",
            sa.String(length=32),
            nullable=False,
            server_default="completed",
        ),
    )
    op.execute(
        """
        UPDATE sites
        SET baseline_status = CASE
            WHEN status = 'initializing' THEN 'pending'
            WHEN status = 'failed' THEN 'failed'
            ELSE 'completed'
        END
        """
    )
    op.alter_column("sites", "baseline_status", server_default=None)
