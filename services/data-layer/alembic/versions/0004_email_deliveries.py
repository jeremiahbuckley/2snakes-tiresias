"""Email deliveries — transactional email dedupe + audit log

Revision ID: 0004
Revises: 0003
Create Date: 2026-04-16 00:00:00.000000

Adds the ``email_deliveries`` table used by notification-service to guarantee
at-most-once delivery per (user, event_type, dedupe_key) and to record
provider message ids for future debugging / support.

"""

from typing import Sequence, Union

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql
from alembic import op

revision: str = "0004"
down_revision: Union[str, None] = "0003"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "email_deliveries",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            nullable=False,
        ),
        sa.Column(
            "user_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("event_type", sa.String(64), nullable=False),
        sa.Column("dedupe_key", sa.String(256), nullable=False),
        sa.Column("provider_message_id", sa.String(128), nullable=True),
        sa.Column(
            "status",
            sa.String(16),
            nullable=False,
            server_default="sent",
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.UniqueConstraint(
            "user_id",
            "event_type",
            "dedupe_key",
            name="uq_email_delivery_dedupe",
        ),
    )
    # Supporting index on user_id for "show me a user's delivery log" queries
    # and FK-side cascade lookups. (The composite unique constraint covers
    # the primary dedupe lookup path.)
    op.create_index(
        "ix_email_deliveries_user_id",
        "email_deliveries",
        ["user_id"],
    )


def downgrade() -> None:
    op.drop_index("ix_email_deliveries_user_id", table_name="email_deliveries")
    op.drop_table("email_deliveries")
