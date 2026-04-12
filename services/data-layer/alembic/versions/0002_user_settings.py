"""User settings — linked_accounts, share_tokens, notification_preferences

Revision ID: 0002
Revises: 0001
Create Date: 2026-04-12 00:00:00.000000

Adds three tables:

linked_accounts
  One row per (user, platform) pair.  Covers both prediction-market data
  sources (kalshi, polymarket, manifold, metaculus) and social publishing
  targets (x, bluesky).

share_tokens
  Anonymous share-link slugs that let a user share scores / badges
  without revealing their identity.

notification_preferences
  Per-user email notification toggles (1:1 with users).
"""

from typing import Sequence, Union

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql
from alembic import op

revision: str = "0002"
down_revision: Union[str, None] = "0001"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:

    # ------------------------------------------------------------------
    # linked_accounts
    # ------------------------------------------------------------------
    op.create_table(
        "linked_accounts",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "user_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        # "kalshi" | "polymarket" | "manifold" | "metaculus" | "x" | "bluesky"
        sa.Column("platform", sa.String(32), nullable=False),
        # "market" | "social"
        sa.Column("platform_type", sa.String(16), nullable=False),
        # Username, wallet address, DID, etc.
        sa.Column("external_identifier", sa.String(256), nullable=True),
        # Encrypted API key / OAuth token / app password (ciphertext only)
        sa.Column("credential_encrypted", sa.Text(), nullable=True),
        # Whether to pull (market) or push (social) for this platform
        sa.Column("is_enabled", sa.Boolean(), nullable=False, server_default="true"),
        # Set to true once credential has been verified via the platform's API
        sa.Column("is_verified", sa.Boolean(), nullable=False, server_default="false"),
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
        sa.UniqueConstraint("user_id", "platform", name="uq_linked_accounts_user_platform"),
    )
    op.create_index("ix_linked_accounts_user_id", "linked_accounts", ["user_id"])

    # ------------------------------------------------------------------
    # share_tokens
    # ------------------------------------------------------------------
    op.create_table(
        "share_tokens",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "user_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("token", sa.String(64), nullable=False),
        sa.Column("label", sa.String(128), nullable=True),
        sa.Column("show_scores", sa.Boolean(), nullable=False, server_default="true"),
        sa.Column("show_badges", sa.Boolean(), nullable=False, server_default="true"),
        sa.Column("show_predictions", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default="true"),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=True),
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
    op.create_index("ix_share_tokens_user_id", "share_tokens", ["user_id"])
    op.create_index("ix_share_tokens_token", "share_tokens", ["token"], unique=True)

    # ------------------------------------------------------------------
    # notification_preferences
    # ------------------------------------------------------------------
    op.create_table(
        "notification_preferences",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "user_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("email_on_resolution", sa.Boolean(), nullable=False, server_default="true"),
        sa.Column("email_on_badge", sa.Boolean(), nullable=False, server_default="true"),
        sa.Column("email_on_rank_change", sa.Boolean(), nullable=False, server_default="false"),
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
    op.create_index(
        "ix_notification_preferences_user_id",
        "notification_preferences",
        ["user_id"],
        unique=True,
    )


def downgrade() -> None:
    op.drop_table("notification_preferences")
    op.drop_table("share_tokens")
    op.drop_table("linked_accounts")
