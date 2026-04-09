"""Initial schema — users, markets, predictions, user_scores

Revision ID: 0001
Revises:
Create Date: 2026-04-07 00:00:00.000000

"""
from typing import Sequence, Union

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql
from alembic import op

revision: str = "0001"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


market_outcome = sa.Enum("yes", "no", "ambiguous", name="market_outcome")


def upgrade() -> None:

    # ------------------------------------------------------------------
    # users
    # ------------------------------------------------------------------
    op.create_table(
        "users",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("email", sa.String(320), nullable=False),
        sa.Column("username", sa.String(64), nullable=False),
        sa.Column("hashed_password", sa.String(256), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default="true"),
        sa.Column("is_verified", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("display_name", sa.String(128), nullable=True),
        sa.Column("bio", sa.Text(), nullable=True),
        sa.Column("avatar_url", sa.String(2048), nullable=True),
        sa.Column("social_links", postgresql.JSONB(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
    )
    op.create_index("ix_users_email", "users", ["email"], unique=True)
    op.create_index("ix_users_username", "users", ["username"], unique=True)

    # ------------------------------------------------------------------
    # markets
    # ------------------------------------------------------------------
    op.create_table(
        "markets",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "creator_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("title", sa.String(512), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("resolution_criteria", sa.Text(), nullable=True),
        sa.Column("category", sa.String(128), nullable=True),
        sa.Column("source_url", sa.String(2048), nullable=True),
        sa.Column("closes_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("resolves_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("resolved_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("outcome", market_outcome, nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
    )
    op.create_index("ix_markets_creator_id", "markets", ["creator_id"])
    op.create_index("ix_markets_category", "markets", ["category"])

    # ------------------------------------------------------------------
    # predictions
    # ------------------------------------------------------------------
    op.create_table(
        "predictions",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "user_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "market_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("markets.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("probability", sa.Numeric(precision=6, scale=5), nullable=False),
        sa.Column("rationale", sa.Text(), nullable=True),
        sa.Column("resolved_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("brier_score", sa.Numeric(precision=6, scale=5), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint("probability >= 0.0 AND probability <= 1.0", name="ck_probability_range"),
        sa.CheckConstraint(
            "brier_score IS NULL OR (brier_score >= 0.0 AND brier_score <= 1.0)",
            name="ck_brier_score_range",
        ),
    )
    op.create_index("ix_predictions_user_id", "predictions", ["user_id"])
    op.create_index("ix_predictions_market_id", "predictions", ["market_id"])
    # Enforce one prediction per user per market
    op.create_index(
        "uq_predictions_user_market",
        "predictions",
        ["user_id", "market_id"],
        unique=True,
    )

    # ------------------------------------------------------------------
    # user_scores
    # ------------------------------------------------------------------
    op.create_table(
        "user_scores",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "user_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("total_predictions", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("resolved_predictions", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("brier_score_sum", sa.Numeric(precision=12, scale=5), nullable=True),
        sa.Column("mean_brier_score", sa.Numeric(precision=6, scale=5), nullable=True),
        sa.Column("calibration_score", sa.Numeric(precision=6, scale=5), nullable=True),
        sa.Column("accuracy", sa.Numeric(precision=6, scale=5), nullable=True),
        sa.Column(
            "last_scored_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=True,
        ),
        sa.CheckConstraint("total_predictions >= 0", name="ck_total_predictions_nonneg"),
        sa.CheckConstraint("resolved_predictions >= 0", name="ck_resolved_predictions_nonneg"),
        sa.CheckConstraint("resolved_predictions <= total_predictions", name="ck_resolved_lte_total"),
        sa.CheckConstraint(
            "mean_brier_score IS NULL OR (mean_brier_score >= 0.0 AND mean_brier_score <= 1.0)",
            name="ck_mean_brier_range",
        ),
        sa.CheckConstraint(
            "calibration_score IS NULL OR (calibration_score >= 0.0 AND calibration_score <= 1.0)",
            name="ck_calibration_range",
        ),
        sa.CheckConstraint(
            "accuracy IS NULL OR (accuracy >= 0.0 AND accuracy <= 1.0)",
            name="ck_accuracy_range",
        ),
    )
    op.create_index("ix_user_scores_user_id", "user_scores", ["user_id"], unique=True)


def downgrade() -> None:
    op.drop_table("user_scores")
    op.drop_table("predictions")
    op.drop_table("markets")
    op.drop_table("users")
    market_outcome.drop(op.get_bind())
