"""
CRUD operations for UserScore (leaderboard aggregates).

The main entry point is rebuild_for_user(), which recomputes all stats
from raw prediction data. Call this after resolving a market.

For cheap incremental updates use increment_for_user(), which only
touches the delta without requerying all predictions.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Optional, Sequence
from uuid import UUID

from sqlalchemy import case, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from data.models.prediction import Prediction
from data.models.score import UserScore
from data.schemas.score import UserScorePublic, LeaderboardEntry
from .base import CRUDBase


class ScoreCRUD(CRUDBase[UserScore, UserScorePublic, UserScorePublic]):

    # -------------------------------------------------------------------------
    # Lookups
    # -------------------------------------------------------------------------

    async def get_by_user(self, db: AsyncSession, user_id: UUID) -> Optional[UserScore]:
        result = await db.execute(select(UserScore).where(UserScore.user_id == user_id))
        return result.scalar_one_or_none()

    async def get_or_create(self, db: AsyncSession, user_id: UUID) -> UserScore:
        score = await self.get_by_user(db, user_id)
        if score is None:
            score = UserScore(user_id=user_id)
            db.add(score)
            await db.flush()
            await db.refresh(score)
        return score

    # -------------------------------------------------------------------------
    # Full recompute (accurate but slower)
    # -------------------------------------------------------------------------

    async def rebuild_for_user(self, db: AsyncSession, user_id: UUID) -> UserScore:
        """
        Recompute all stats for a user from scratch using their prediction history.
        Use after bulk imports or when calibration needs recalculating.
        """
        # Aggregate totals in one query
        result = await db.execute(
            select(
                func.count(Prediction.id).label("total"),
                func.count(Prediction.brier_score).label("resolved"),
                func.sum(Prediction.brier_score).label("brier_sum"),
                # Accuracy: predictions where round(probability) matched outcome
                # Proxy: brier_score <= 0.25 means the direction was correct
                func.sum(
                    func.cast(
                        (Prediction.brier_score <= 0.25).cast(
                            type_=None  # Will use DB boolean cast
                        ),
                        sqlalchemy_type=None,
                    )
                ).label("correct"),
            ).where(
                Prediction.user_id == user_id,
            )
        )
        row = result.one()

        score = await self.get_or_create(db, user_id)
        score.total_predictions = row.total or 0
        score.resolved_predictions = row.resolved or 0
        score.brier_score_sum = float(row.brier_sum) if row.brier_sum is not None else None
        score.recompute_mean_brier()

        # Calibration requires a more nuanced calculation —
        # computed via a separate helper that bins probabilities
        score.calibration_score = await self._compute_calibration(db, user_id)
        score.accuracy = await self._compute_accuracy(db, user_id)
        score.last_scored_at = datetime.now(timezone.utc)

        db.add(score)
        await db.flush()
        await db.refresh(score)
        return score

    # -------------------------------------------------------------------------
    # Incremental update (fast, called after each market resolution)
    # -------------------------------------------------------------------------

    async def increment_for_user(
        self,
        db: AsyncSession,
        user_id: UUID,
        *,
        new_brier_scores: list[float],
    ) -> UserScore:
        """
        Apply a batch of newly-computed Brier scores without requerying everything.
        Call this right after PredictionCRUD.resolve_all_for_market().
        """
        score = await self.get_or_create(db, user_id)
        n = len(new_brier_scores)
        if n == 0:
            return score

        score.resolved_predictions = (score.resolved_predictions or 0) + n
        existing_sum = float(score.brier_score_sum or 0.0)
        score.brier_score_sum = existing_sum + sum(new_brier_scores)
        score.recompute_mean_brier()

        # Recalculate calibration & accuracy from scratch (small cost)
        score.calibration_score = await self._compute_calibration(db, user_id)
        score.accuracy = await self._compute_accuracy(db, user_id)
        score.last_scored_at = datetime.now(timezone.utc)

        db.add(score)
        await db.flush()
        await db.refresh(score)
        return score

    # -------------------------------------------------------------------------
    # Leaderboard
    # -------------------------------------------------------------------------

    async def leaderboard(
        self,
        db: AsyncSession,
        *,
        skip: int = 0,
        limit: int = 50,
        min_resolved: int = 5,
    ) -> list[LeaderboardEntry]:
        """
        Return ranked users by mean Brier score (lower = better).
        Only include users with at least `min_resolved` resolved predictions.
        """
        from data.models.user import User

        result = await db.execute(
            select(
                UserScore,
                User.username,
                User.display_name,
                User.avatar_url,
            )
            .join(User, UserScore.user_id == User.id)
            .where(
                UserScore.resolved_predictions >= min_resolved,
                UserScore.mean_brier_score.isnot(None),
            )
            .order_by(UserScore.mean_brier_score.asc())
            .offset(skip)
            .limit(limit)
        )
        rows = result.all()

        entries = []
        for rank, row in enumerate(rows, start=skip + 1):
            score_obj, username, display_name, avatar_url = row
            entries.append(
                LeaderboardEntry(
                    rank=rank,
                    user_id=score_obj.user_id,
                    username=username,
                    display_name=display_name,
                    avatar_url=avatar_url,
                    total_predictions=score_obj.total_predictions,
                    resolved_predictions=score_obj.resolved_predictions,
                    mean_brier_score=score_obj.mean_brier_score,
                    calibration_score=score_obj.calibration_score,
                    accuracy=score_obj.accuracy,
                )
            )
        return entries

    # -------------------------------------------------------------------------
    # Private stat helpers
    # -------------------------------------------------------------------------

    async def _compute_accuracy(self, db: AsyncSession, user_id: UUID) -> Optional[float]:
        """
        Directional accuracy: fraction of resolved predictions where
        round(probability) matched the binary outcome.
        Brier score <= 0.25 ⟺ direction was correct.
        """
        result = await db.execute(
            select(
                func.count(Prediction.id).label("total"),
                func.sum(
                    case(
                        (Prediction.brier_score <= 0.25, 1),
                        else_=0,
                    )
                ).label("correct"),
            ).where(
                Prediction.user_id == user_id,
                Prediction.brier_score.isnot(None),
            )
        )
        row = result.one()
        if not row.total:
            return None
        return round(float(row.correct) / float(row.total), 5)

    async def _compute_calibration(self, db: AsyncSession, user_id: UUID) -> Optional[float]:
        """
        Calibration score using the Expected Calibration Error (ECE) mapped to [0,1].

        Bins predictions into deciles [0-0.1), [0.1-0.2), ..., [0.9-1.0].
        For each bin, computes |mean_probability - fraction_correct|.
        ECE = weighted average of per-bin errors.
        calibration_score = 1 - ECE  (so 1 is perfect).
        """
        from sqlalchemy import Float, Integer, cast, literal_column

        result = await db.execute(
            select(Prediction.probability, Prediction.brier_score).where(
                Prediction.user_id == user_id,
                Prediction.brier_score.isnot(None),
            )
        )
        rows = result.all()
        if not rows:
            return None

        # Python-side binning (avoids complex DB-level window functions)
        bins: dict[int, list[tuple[float, bool]]] = {i: [] for i in range(10)}
        for prob, brier in rows:
            p = float(prob)
            correct = float(brier) <= 0.25  # direction correct
            bin_idx = min(int(p * 10), 9)
            bins[bin_idx].append((p, correct))

        ece = 0.0
        n_total = len(rows)
        for bin_data in bins.values():
            if not bin_data:
                continue
            n_bin = len(bin_data)
            mean_p = sum(p for p, _ in bin_data) / n_bin
            frac_correct = sum(1 for _, c in bin_data if c) / n_bin
            ece += (n_bin / n_total) * abs(mean_p - frac_correct)

        return round(max(0.0, 1.0 - ece), 5)


ScoreCRUD = ScoreCRUD(UserScore)
