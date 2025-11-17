"""Add analytics tables for features and statistical tests."""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0003_add_analytics_tables"
down_revision: str | None = "0002_add_content_tables"
branch_labels: Sequence[str] | None = None
depends_on: Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "features",
        sa.Column("symbol", sa.String(length=16), nullable=False),
        sa.Column("feature_name", sa.String(length=128), nullable=False),
        sa.Column("ts", sa.DateTime(timezone=True), nullable=False),
        sa.Column("value", sa.Numeric(24, 12), nullable=False),
        sa.ForeignKeyConstraint(["symbol"], ["instruments.symbol"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("symbol", "feature_name", "ts", name="pk_features"),
    )
    op.create_index(
        "ix_features_symbol_feature_name_ts",
        "features",
        ["symbol", "feature_name", "ts"],
    )

    op.create_table(
        "lead_lag",
        sa.Column("leader", sa.String(length=16), nullable=False),
        sa.Column("follower", sa.String(length=16), nullable=False),
        sa.Column("window", sa.String(length=32), nullable=False),
        sa.Column("computed_ts", sa.DateTime(timezone=True), nullable=False),
        sa.Column("best_lag_min", sa.Integer(), nullable=False),
        sa.Column("strength", sa.Numeric(12, 6), nullable=False),
        sa.ForeignKeyConstraint(
            ["leader"],
            ["instruments.symbol"],
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["follower"],
            ["instruments.symbol"],
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint(
            "leader",
            "follower",
            "window",
            "computed_ts",
            name="pk_lead_lag",
        ),
    )
    op.create_index(
        "ix_lead_lag_pair_window_ts",
        "lead_lag",
        ["leader", "follower", "window", "computed_ts"],
    )

    op.create_table(
        "granger_tests",
        sa.Column("x_symbol", sa.String(length=16), nullable=False),
        sa.Column("y_symbol", sa.String(length=16), nullable=False),
        sa.Column("window", sa.String(length=32), nullable=False),
        sa.Column("computed_ts", sa.DateTime(timezone=True), nullable=False),
        sa.Column("p_value", sa.Numeric(12, 6), nullable=False),
        sa.Column("direction", sa.String(length=16), nullable=False),
        sa.ForeignKeyConstraint(
            ["x_symbol"],
            ["instruments.symbol"],
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["y_symbol"],
            ["instruments.symbol"],
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint(
            "x_symbol",
            "y_symbol",
            "window",
            "computed_ts",
            name="pk_granger_tests",
        ),
    )
    op.create_index(
        "ix_granger_tests_pair_window_ts",
        "granger_tests",
        ["x_symbol", "y_symbol", "window", "computed_ts"],
    )


def downgrade() -> None:
    op.drop_index("ix_granger_tests_pair_window_ts", table_name="granger_tests")
    op.drop_table("granger_tests")

    op.drop_index("ix_lead_lag_pair_window_ts", table_name="lead_lag")
    op.drop_table("lead_lag")

    op.drop_index("ix_features_symbol_feature_name_ts", table_name="features")
    op.drop_table("features")
