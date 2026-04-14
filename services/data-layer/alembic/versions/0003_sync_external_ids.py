"""Sync external IDs — markets, predictions, badge tracking

Revision ID: 0003
Revises: 0002
Create Date: 2026-04-13 00:00:00.000000

Adds columns that let the scheduler import and deduplicate data from external
prediction-market platforms:

  markets
    source      — platform name ("kalshi" | "manifold" | "metaculus" | "polymarket")
    external_id — platform-assigned market ID (ticker, contract ID, slug, etc.)
    Partial unique index on (source, external_id) WHERE both NOT NULL.

  predictions
    source      — platform this prediction was imported from
    external_id — platform-assigned bet/fill/forecast ID

  user_scores
    badge_ids   — JSONB list of badge ID strings the user currently holds

"""

from typing import Sequence, Union

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql
from alembic import op

revision: str = "0003"
down_revision: Union[str, None] = "0002"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:

    # ------------------------------------------------------------------
    # markets — add source + external_id
    # ------------------------------------------------------------------
    op.add_column("markets", sa.Column("source", sa.String(32), nullable=True))
    op.add_column("markets", sa.Column("external_id", sa.String(512), nullable=True))

    op.create_index("ix_markets_source", "markets", ["source"])

    # Partial unique index: only enforced when both columns are non-NULL.
    # (Manually-created markets have source=NULL and are unaffected.)
    op.create_index(
        "uq_market_source_external",
        "markets",
        ["source", "external_id"],
        unique=True,
        postgresql_where="source IS NOT NULL AND external_id IS NOT NULL",
    )

    # ------------------------------------------------------------------
    # predictions — add source + external_id
    # ------------------------------------------------------------------
    op.add_column("predictions", sa.Column("source", sa.String(32), nullable=True))
    op.add_column("predictions", sa.Column("external_id", sa.String(512), nullable=True))

    op.create_index("ix_predictions_source", "predictions", ["source"])

    # ------------------------------------------------------------------
    # user_scores — add badge_ids
    # ------------------------------------------------------------------
    op.add_column(
        "user_scores",
        sa.Column(
            "badge_ids",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=True,
            comment="List of badge ID strings the user currently holds.",
        ),
    )


def downgrade() -> None:
    op.drop_column("user_scores", "badge_ids")

    op.drop_index("ix_predictions_source", "predictions")
    op.drop_column("predictions", "external_id")
    op.drop_column("predictions", "source")

    op.drop_index("uq_market_source_external", "markets")
    op.drop_index("ix_markets_source", "markets")
    op.drop_column("markets", "external_id")
    op.drop_column("markets", "source")
