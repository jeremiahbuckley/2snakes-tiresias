"""Market tags — replace category with tags ARRAY

Revision ID: 0006
Revises: 0005
Create Date: 2026-04-27

Drops the unused ``category`` column (never populated from sync) and adds
``tags TEXT[] NOT NULL DEFAULT '{}'`` with a GIN index for fast containment
queries (``WHERE 'politics' = ANY(tags)``).
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0006"
down_revision: Union[str, None] = "0005"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.drop_index("ix_markets_category", table_name="markets")
    op.drop_column("markets", "category")
    op.add_column(
        "markets",
        sa.Column(
            "tags",
            postgresql.ARRAY(sa.Text()),
            nullable=False,
            server_default=sa.text("'{}'"),
        ),
    )
    op.create_index(
        "ix_markets_tags",
        "markets",
        ["tags"],
        postgresql_using="gin",
    )


def downgrade() -> None:
    op.drop_index("ix_markets_tags", table_name="markets")
    op.drop_column("markets", "tags")
    op.add_column(
        "markets",
        sa.Column("category", sa.String(128), nullable=True),
    )
    op.create_index("ix_markets_category", "markets", ["category"])
