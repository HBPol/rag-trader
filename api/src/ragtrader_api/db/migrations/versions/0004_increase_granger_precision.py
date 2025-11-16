"""Increase precision of stored Granger test p-values."""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0004_increase_granger_precision"
down_revision: str | None = "0003_add_analytics_tables"
branch_labels: Sequence[str] | None = None
depends_on: Sequence[str] | None = None


def upgrade() -> None:
    op.alter_column(
        "granger_tests",
        "p_value",
        existing_type=sa.Numeric(12, 6),
        type_=sa.Numeric(24, 12),
        existing_nullable=False,
    )


def downgrade() -> None:
    op.alter_column(
        "granger_tests",
        "p_value",
        existing_type=sa.Numeric(24, 12),
        type_=sa.Numeric(12, 6),
        existing_nullable=False,
    )
