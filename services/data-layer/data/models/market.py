"""
Market model — a prediction market question/event that users forecast on.
"""

from __future__ import annotations

import enum
from typing import TYPE_CHECKING, List, Optional
from uuid import UUID

from sqlalchemy import DateTime, Enum, ForeignKey, Index, String, Text, text
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from data.database import Base, TimestampMixin, new_uuid

if TYPE_CHECKING:
    from .user import User
    from .prediction import Prediction


class MarketOutcome(str, enum.Enum):
    """Possible resolutions for a binary prediction market."""
    YES = "yes"
    NO = "no"
    AMBIGUOUS = "ambiguous"  # resolved but outcome unclear / voided


class Market(TimestampMixin, Base):
    __tablename__ = "markets"
    __table_args__ = (
        # Partial unique index: prevents duplicate imports from the same platform.
        # Only enforced when both columns are non-NULL (manually-created markets
        # have source=NULL and are not affected).
        Index(
            "uq_market_source_external",
            "source",
            "external_id",
            unique=True,
            postgresql_where=text("source IS NOT NULL AND external_id IS NOT NULL"),
        ),
    )

    # -------------------------------------------------------------------------
    # Identity
    # -------------------------------------------------------------------------
    id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        primary_key=True,
        default=new_uuid,
    )
    creator_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )

    # -------------------------------------------------------------------------
    # External sync identifiers
    # -------------------------------------------------------------------------
    source: Mapped[Optional[str]] = mapped_column(
        String(32),
        nullable=True,
        index=True,
        doc="Platform this market was imported from: 'kalshi' | 'manifold' | 'metaculus' | 'polymarket'. NULL for manually-created markets.",
    )
    external_id: Mapped[Optional[str]] = mapped_column(
        String(512),
        nullable=True,
        doc="The platform's own identifier for this market (ticker, contract ID, slug, etc.).",
    )

    # -------------------------------------------------------------------------
    # Content
    # -------------------------------------------------------------------------
    title: Mapped[str] = mapped_column(String(512), nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    resolution_criteria: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    category: Mapped[Optional[str]] = mapped_column(String(128), nullable=True, index=True)
    source_url: Mapped[Optional[str]] = mapped_column(String(2048), nullable=True)

    # -------------------------------------------------------------------------
    # Lifecycle
    # -------------------------------------------------------------------------
    closes_at: Mapped[Optional[DateTime]] = mapped_column(
        DateTime(timezone=True), nullable=True,
        doc="No new predictions accepted after this time.",
    )
    resolves_at: Mapped[Optional[DateTime]] = mapped_column(
        DateTime(timezone=True), nullable=True,
        doc="Expected resolution date (informational).",
    )
    resolved_at: Mapped[Optional[DateTime]] = mapped_column(
        DateTime(timezone=True), nullable=True,
        doc="Actual timestamp the market was resolved.",
    )
    outcome: Mapped[Optional[MarketOutcome]] = mapped_column(
        Enum(MarketOutcome, name="market_outcome", values_callable=lambda obj: [e.value for e in obj]),
        nullable=True,
        doc="NULL means unresolved.",
    )

    # -------------------------------------------------------------------------
    # Relationships
    # -------------------------------------------------------------------------
    creator: Mapped[Optional["User"]] = relationship("User", back_populates="markets")
    predictions: Mapped[List["Prediction"]] = relationship(
        "Prediction", back_populates="market", cascade="all, delete-orphan", lazy="selectin"
    )

    # -------------------------------------------------------------------------
    # Computed helpers
    # -------------------------------------------------------------------------
    @property
    def is_resolved(self) -> bool:
        return self.outcome is not None

    @property
    def is_open(self) -> bool:
        from datetime import datetime, timezone
        if self.is_resolved:
            return False
        if self.closes_at and datetime.now(timezone.utc) > self.closes_at:
            return False
        return True

    def __repr__(self) -> str:
        return f"<Market id={self.id} title={self.title!r} outcome={self.outcome}>"
