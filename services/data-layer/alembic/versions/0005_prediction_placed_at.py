"""Prediction placed_at — actual forecast timestamp from source platform

Revision ID: 0005
Revises: 0004
Create Date: 2026-04-26 00:00:00.000000

Adds ``placed_at`` (TIMESTAMPTZ, nullable) to the predictions table.
Populated by connectors from the platform's own forecast timestamp so that
predictions can be sorted by when the user actually made them rather than
by the database insertion time (created_at).

Existing rows keep placed_at = NULL and fall back to created_at for ordering.
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0005"
down_revision: Union[str, None] = "0004"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "predictions",
        sa.Column("placed_at", sa.DateTime(timezone=True), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("predictions", "placed_at")
