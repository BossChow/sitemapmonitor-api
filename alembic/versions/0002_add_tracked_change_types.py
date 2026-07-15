"""add tracked change types

Revision ID: 0002_add_tracked_change_types
Revises: 0001_initial
Create Date: 2026-07-14 00:00:00.000000
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "0002_add_tracked_change_types"
down_revision: str | None = "0001_initial"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "sites",
        sa.Column(
            "tracked_change_types",
            sa.JSON(),
            nullable=False,
            server_default=sa.text("'[\"added\", \"removed\", \"updated\"]'::json"),
        ),
    )
    op.alter_column("sites", "tracked_change_types", server_default=None)


def downgrade() -> None:
    op.drop_column("sites", "tracked_change_types")
