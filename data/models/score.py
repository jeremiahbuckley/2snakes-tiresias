"""
UserScore model — aggregated forecasting statistics per user.

This table is a denormalized cache updated whenever a market resolves.
The raw data always lives in the predictions table; this is the leaderboard view.

Metrics stored:
  - mean_brier_score       lower is better (0 = perfect, 1 = worst)
  - calibration_score      how well probability bands match actual frequencies
                           1.0 = perfectly calibrated, 0.0 = maximally miscalibrated
  - resolution_rate        fraction of predictions that have been resolved
  - accuracy               fraction of predictions where round(probability) matched outcome
                           (directional accuracy, ignores confidence)
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Optional
from uuid import UUID

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, Integer, Numeric, func
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from data.database import Base, new_uuid

if TYPE_CHECKING:
    from .user import User


class UserScore(Base):
    __tablename__ = "user_scores"
    __table_args__ = (
        CheckConstraint("total_predictions >= 0", name="ck_total_predictions_nonneg"),
        CheckConstraint("resolved_predictions >= 0", name="ck_resolved_predictions_nonneg"),
        CheckConstraint("resolved_predictions <= total_predictions", name="ck_resolved_lte_total"),
        CheckConstraint(
            "mean_brier_score IS NULL OR (mean_brier_score >= 0.0 AND mean_brier_score <= 1.0)",
            name="ck_mean_brier_range",
        ),
        CheckConstraint(
            "calibration_score IS NULL OR (calibration_score >= 0.0 AND calibration_score <= 1.0)",
            name="ck_calibration_range",
        ),
        CheckConstraint(
            "accuracy IS NULL OR (accuracy >= 0.0 AND accuracy <= 1.0)",
            name="ck_accuracy_range",
        ),
    )

    # -------------------------------------------------------------------------
    # Identity (one row per user)
    # -------------------------------------------------------------------------
    id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        primary_key=True,
        default=new_uuid,
    )
    user_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        unique=True,
        nullable=False,
        index=True,
    )

    # -------------------------------------------------------------------------
    # Counters (updated incrementally)
    # -------------------------------------------------------------------------
    total_predictions: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    resolved_predictions: Mapped[int] = mapped_column(Integer, default=0, nullable=False)

    # Brier score sum makes it cheap to recompute the running mean
    brier_score_sum: Mapped[Optional[float]] = mapped_column(
        Numeric(precision=12, scale=5), nullable=True, default=None
    )

    # -------------------------------------------------------------------------
    # Derived stats (recomputed on each resolution event)
    # -------------------------------------------------------------------------
    mean_brier_score: Mapped[Optional[float]] = mapped_column(
        Numeric(precision=6, scale=5), nullable=True
    )
    calibration_score: Mapped[Optional[float]] = mapped_column(
        Numeric(precision=6, scale=5), nullable=True
    )
    accuracy: Mapped[Optional[float]] = mapped_column(
        Numeric(precision=6, scale=5), nullable=True
    )

    # -------------------------------------------------------------------------
    # Housekeeping
    # -------------------------------------------------------------------------
    last_scored_at: Mapped[Optional[DateTime]] = mapped_column(
        DateTime(timezone=True), nullable=True, server_default=func.now()
    )

    # -------------------------------------------------------------------------
    # Relationships
    # -------------------------------------------------------------------------
    user: Mapped["User"] = relationship("User", back_populates="score")

    # -------------------------------------------------------------------------
    # Helpers
    # -------------------------------------------------------------------------
    @property
    def resolution_rate(self) -> Optional[float]:
        if self.total_predictions == 0:
            return None
        return self.resolved_predictions / self.total_predictions

    def recompute_mean_brier(self) -> None:
        """Recompute mean_brier_score from running sum."""
        if self.resolved_predictions and self.brier_score_sum is not None:
            self.mean_brier_score = float(self.brier_score_sum) / self.resolved_predictions
        else:
            self.mean_brier_score = None

    def __repr__(self) -> str:
        return (
            f"<UserScore user={self.user_id} "
            f"n={self.resolved_predictions}/{self.total_predictions} "
            f"brier={self.mean_brier_score}>"
        )
