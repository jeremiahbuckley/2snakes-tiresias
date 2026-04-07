"""
Prediction model — a single probability forecast by a user on a market.

Brier score is stored at resolution time so historical scores are immutable
even if the scoring formula changes.

  Brier score = (probability - outcome)²
  where outcome ∈ {0.0, 1.0}  (NO=0, YES=1)
  Lower is better; perfect = 0.0, worst = 1.0.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Optional
from uuid import UUID

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, Numeric, Text
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from data.database import Base, TimestampMixin, new_uuid

if TYPE_CHECKING:
    from .user import User
    from .market import Market


class Prediction(TimestampMixin, Base):
    __tablename__ = "predictions"
    __table_args__ = (
        # Probability must be in [0, 1]
        CheckConstraint("probability >= 0.0 AND probability <= 1.0", name="ck_probability_range"),
        # Brier score must be in [0, 1] when present
        CheckConstraint(
            "brier_score IS NULL OR (brier_score >= 0.0 AND brier_score <= 1.0)",
            name="ck_brier_score_range",
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
    user_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    market_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("markets.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    # -------------------------------------------------------------------------
    # Forecast
    # -------------------------------------------------------------------------
    # Stored with enough precision for calibration analysis
    probability: Mapped[float] = mapped_column(
        Numeric(precision=6, scale=5),
        nullable=False,
        doc="Probability assigned to YES outcome, in [0, 1].",
    )
    rationale: Mapped[Optional[str]] = mapped_column(
        Text, nullable=True, doc="Optional public explanation for the prediction."
    )

    # -------------------------------------------------------------------------
    # Resolution snapshot
    # -------------------------------------------------------------------------
    resolved_at: Mapped[Optional[DateTime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        doc="Timestamp this prediction was scored.",
    )
    brier_score: Mapped[Optional[float]] = mapped_column(
        Numeric(precision=6, scale=5),
        nullable=True,
        doc="(probability - outcome)²; populated when the market resolves.",
    )

    # -------------------------------------------------------------------------
    # Relationships
    # -------------------------------------------------------------------------
    user: Mapped["User"] = relationship("User", back_populates="predictions")
    market: Mapped["Market"] = relationship("Market", back_populates="predictions")

    # -------------------------------------------------------------------------
    # Helpers
    # -------------------------------------------------------------------------
    @property
    def is_resolved(self) -> bool:
        return self.brier_score is not None

    def compute_brier_score(self, outcome_is_yes: bool) -> float:
        """Compute and store the Brier score for this prediction."""
        outcome = 1.0 if outcome_is_yes else 0.0
        score = float((float(self.probability) - outcome) ** 2)
        self.brier_score = score
        return score

    def __repr__(self) -> str:
        return (
            f"<Prediction id={self.id} user={self.user_id} "
            f"market={self.market_id} p={self.probability} brier={self.brier_score}>"
        )
