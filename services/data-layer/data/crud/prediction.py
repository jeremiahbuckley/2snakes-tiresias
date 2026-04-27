"""
CRUD operations for Prediction.

Key invariants enforced here:
  - A user may have at most one active prediction per market.
  - Probability is immutable after creation (only rationale can be updated).
  - resolve_all_for_market() scores every unresolved prediction in one pass.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Optional, Sequence
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from data.models.market import Market, MarketOutcome
from data.models.prediction import Prediction
from data.schemas.prediction import PredictionCreate, PredictionUpdate
from .base import CRUDBase


class PredictionCRUD(CRUDBase[Prediction, PredictionCreate, PredictionUpdate]):

    async def create(  # type: ignore[override]
        self,
        db: AsyncSession,
        *,
        obj_in: PredictionCreate,
        user_id: UUID,
    ) -> Prediction:
        """
        Create a new prediction, enforcing one-per-user-per-market.
        Raises ValueError if the user already has a prediction on this market.
        """
        existing = await self.get_by_user_and_market(db, user_id=user_id, market_id=obj_in.market_id)
        if existing:
            raise ValueError(
                f"User {user_id} already has a prediction on market {obj_in.market_id}. "
                "Update the existing prediction instead."
            )
        prediction = Prediction(
            user_id=user_id,
            market_id=obj_in.market_id,
            probability=obj_in.probability,
            rationale=obj_in.rationale,
        )
        db.add(prediction)
        await db.flush()
        await db.refresh(prediction)
        return prediction

    async def get_by_user_and_market(
        self,
        db: AsyncSession,
        *,
        user_id: UUID,
        market_id: UUID,
    ) -> Optional[Prediction]:
        result = await db.execute(
            select(Prediction).where(
                Prediction.user_id == user_id,
                Prediction.market_id == market_id,
            )
        )
        return result.scalar_one_or_none()

    async def list_by_user(
        self,
        db: AsyncSession,
        user_id: UUID,
        *,
        resolved_only: bool = False,
        skip: int = 0,
        limit: int = 100,
    ) -> Sequence[Prediction]:
        stmt = (
            select(Prediction)
            .where(Prediction.user_id == user_id)
            .offset(skip)
            .limit(limit)
            .order_by(Prediction.created_at.desc())
        )
        if resolved_only:
            stmt = stmt.where(Prediction.brier_score.isnot(None))
        result = await db.execute(stmt)
        return result.scalars().all()

    async def list_by_market(
        self,
        db: AsyncSession,
        market_id: UUID,
        *,
        skip: int = 0,
        limit: int = 200,
    ) -> Sequence[Prediction]:
        result = await db.execute(
            select(Prediction)
            .where(Prediction.market_id == market_id)
            .offset(skip)
            .limit(limit)
            .order_by(Prediction.created_at.asc())
        )
        return result.scalars().all()

    # -------------------------------------------------------------------------
    # Connector sync methods
    # -------------------------------------------------------------------------

    async def upsert_from_sync(
        self,
        db: AsyncSession,
        *,
        normalized: dict,
        user_id: UUID,
        market_id: UUID,
    ) -> Optional["Prediction"]:
        """
        Create or update a prediction from a connector-normalized bet/fill/forecast dict.

        The unique key is (user_id, market_id) — one prediction per user per market,
        consistent with the existing constraint.

        Rules:
        - If no prediction exists for (user_id, market_id), create one.
        - If a synced prediction already exists (source IS NOT NULL), update its
          probability to reflect the latest bet (most recently synced wins).
        - If a manually-entered prediction exists (source IS NULL), leave it
          untouched so users' deliberate entries are never overwritten.
        - If predicted_probability is None the record is skipped (returns None).

        Returns the created/updated Prediction, or None if skipped.
        """
        probability = normalized.get("predicted_probability")
        if probability is None:
            return None

        probability = round(float(probability), 5)
        source = normalized.get("source")
        external_id = normalized.get("external_id")

        placed_at = normalized.get("placed_at")
        existing = await self.get_by_user_and_market(db, user_id=user_id, market_id=market_id)

        if existing is not None:
            if existing.source is None:
                # Manual prediction — never overwrite
                return existing
            # Synced prediction — refresh probability and tracking fields
            existing.probability = probability
            existing.source = source
            existing.external_id = external_id
            if placed_at is not None:
                existing.placed_at = placed_at
            db.add(existing)
            await db.flush()
            await db.refresh(existing)
            return existing

        # No existing prediction — create
        prediction = Prediction(
            user_id=user_id,
            market_id=market_id,
            probability=probability,
            source=source,
            external_id=external_id,
            placed_at=placed_at,
        )
        db.add(prediction)
        await db.flush()
        await db.refresh(prediction)
        return prediction

    async def resolve_all_for_market(
        self,
        db: AsyncSession,
        market: Market,
    ) -> list[Prediction]:
        """
        Score every unresolved prediction for a resolved market.
        Returns the list of updated Prediction objects.
        Raises ValueError if the market is not yet resolved.
        """
        if not market.is_resolved or market.outcome == MarketOutcome.AMBIGUOUS:
            # Ambiguous markets don't get scored
            return []

        outcome_is_yes = market.outcome == MarketOutcome.YES
        now = datetime.now(timezone.utc)

        result = await db.execute(
            select(Prediction).where(
                Prediction.market_id == market.id,
                Prediction.brier_score.is_(None),
            )
        )
        predictions = list(result.scalars().all())

        for pred in predictions:
            pred.compute_brier_score(outcome_is_yes)
            pred.resolved_at = now
            db.add(pred)

        await db.flush()
        return predictions


PredictionCRUD = PredictionCRUD(Prediction)
