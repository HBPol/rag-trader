"""Add articles and sentiments tables."""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0002_add_content_tables"
down_revision: str | None = "0001"
branch_labels: Sequence[str] | None = None
depends_on: Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "articles",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("source", sa.String(length=64), nullable=False),
        sa.Column("url", sa.String(length=1024), nullable=False),
        sa.Column("title", sa.String(length=512), nullable=False),
        sa.Column("published_ts", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "fetched_ts",
            sa.DateTime(timezone=True),
            server_default=sa.text("CURRENT_TIMESTAMP"),
            nullable=False,
        ),
        sa.Column("body_excerpt", sa.Text(), nullable=True),
        sa.Column(
            "coins",
            sa.dialects.postgresql.ARRAY(sa.String(length=32)),
            server_default=sa.text("'{}'::varchar[]"),
            nullable=False,
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("CURRENT_TIMESTAMP"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("CURRENT_TIMESTAMP"),
            server_onupdate=sa.text("CURRENT_TIMESTAMP"),
            nullable=False,
        ),
    )

    op.create_index(
        "ix_articles_url_unique",
        "articles",
        ["url"],
        unique=True,
    )

    op.create_table(
        "sentiments",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("article_id", sa.Integer(), nullable=False),
        sa.Column("coin", sa.String(length=16), nullable=False),
        sa.Column("polarity", sa.Numeric(6, 5), nullable=False),
        sa.Column(
            "aspects",
            sa.dialects.postgresql.ARRAY(sa.String(length=64)),
            server_default=sa.text("'{}'::varchar[]"),
            nullable=False,
        ),
        sa.Column("confidence", sa.Numeric(6, 5), nullable=False),
        sa.Column("ts", sa.DateTime(timezone=True), nullable=True),
        sa.Column("zscore_window", sa.Integer(), nullable=False),
        sa.Column("zscore", sa.Numeric(10, 5), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("CURRENT_TIMESTAMP"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("CURRENT_TIMESTAMP"),
            server_onupdate=sa.text("CURRENT_TIMESTAMP"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["article_id"], ["articles.id"], ondelete="CASCADE"),
    )

    op.create_index(
        "ix_sentiments_coin_window_ts",
        "sentiments",
        ["coin", "zscore_window", "ts"],
    )


def downgrade() -> None:
    op.drop_index("ix_sentiments_coin_window_ts", table_name="sentiments")
    op.drop_table("sentiments")
    op.drop_index("ix_articles_url_unique", table_name="articles")
    op.drop_table("articles")
