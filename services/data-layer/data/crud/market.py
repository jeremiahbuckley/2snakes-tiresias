"""
CRUD operations for Market.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Optional, Sequence
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from data.models.market import Market, MarketOutcome
from data.schemas.market import MarketCreate, MarketUpdate
from .base import CRUDBase


class MarketCRUD(CRUDBase[Market, MarketCreate, MarketUpdate]):

    async def create(  # type: ignore[override]
        self,
        db: AsyncSession,
        *,
        obj_in: MarketCreate,
        creator_id: UUID,
    ) -> Market:
        market = Market(
            creator_id=creator_id,
            **obj_in.model_dump(),
        )
        db.add(market)
        await db.flush()
        await db.refresh(market)
        return market

    async def list_open(
        self,
        db: AsyncSession,
        *,
        skip: int = 0,
        limit: int = 50,
        tag: Optional[str] = None,
    ) -> Sequence[Market]:
        """Return markets that are not yet resolved."""
        stmt = (
            select(Market)
            .where(Market.outcome.is_(None))
            .offset(skip)
            .limit(limit)
            .order_by(Market.created_at.desc())
        )
        if tag:
            stmt = stmt.where(Market.tags.contains([tag]))
        result = await db.execute(stmt)
        return result.scalars().all()

    async def list_by_creator(
        self,
        db: AsyncSession,
        creator_id: UUID,
        *,
        skip: int = 0,
        limit: int = 50,
    ) -> Sequence[Market]:
        result = await db.execute(
            select(Market)
            .where(Market.creator_id == creator_id)
            .offset(skip)
            .limit(limit)
            .order_by(Market.created_at.desc())
        )
        return result.scalars().all()

    async def resolve(
        self,
        db: AsyncSession,
        market: Market,
        outcome: MarketOutcome,
    ) -> Market:
        """
        Mark a market as resolved. Scoring individual predictions is handled
        by PredictionCRUD.resolve_all_for_market() called after this.
        """
        market.outcome = outcome
        market.resolved_at = datetime.now(timezone.utc)
        db.add(market)
        await db.flush()
        await db.refresh(market)
        return market

    # -------------------------------------------------------------------------
    # Connector sync methods
    # -------------------------------------------------------------------------

    async def get_by_external(
        self,
        db: AsyncSession,
        *,
        source: str,
        external_id: str,
    ) -> Optional[Market]:
        """Look up a market by its platform origin and platform-assigned ID."""
        result = await db.execute(
            select(Market).where(
                Market.source == source,
                Market.external_id == external_id,
            )
        )
        return result.scalar_one_or_none()

    async def upsert_from_sync(
        self,
        db: AsyncSession,
        *,
        normalized: dict,
    ) -> Market:
        """
        Create or update a market from a connector-normalized dict.

        The normalized dict must include 'source' and 'external_id'.
        Existing markets are updated with fresh metadata. Resolution is applied
        only once — a market that is already resolved locally is not altered.

        Returns the created or updated Market.
        """
        source = normalized["source"]
        external_id = normalized["external_id"]

        market = await self.get_by_external(db, source=source, external_id=external_id)

        if market is None:
            title = normalized.get("title") or f"[{source}] {external_id}"
            market = Market(
                source=source,
                external_id=external_id,
                title=title,
                description=normalized.get("description"),
                resolution_criteria=normalized.get("resolution_criteria"),
                closes_at=normalized.get("closes_at"),
                resolves_at=normalized.get("resolves_at"),
                tags=normalized.get("tags", []),
            )
        else:
            # Refresh mutable metadata fields
            if normalized.get("title"):
                market.title = normalized["title"]
            if normalized.get("description") is not None:
                market.description = normalized["description"]
            if normalized.get("resolution_criteria") is not None:
                market.resolution_criteria = normalized["resolution_criteria"]
            if normalized.get("closes_at") is not None:
                market.closes_at = normalized["closes_at"]
            if normalized.get("resolves_at") is not None:
                market.resolves_at = normalized["resolves_at"]
            incoming_tags = normalized.get("tags", [])
            if incoming_tags:
                market.tags = incoming_tags

        # Apply resolution if the market resolved on the platform and is not
        # already resolved locally (avoids overwriting a manual resolution).
        if normalized.get("resolved") and not market.is_resolved:
            outcome = _map_outcome(source, normalized.get("outcome"))
            if outcome is not None:
                market.outcome = outcome
                market.resolved_at = datetime.now(timezone.utc)

        db.add(market)
        await db.flush()
        await db.refresh(market)
        return market

    async def list_resolved_with_unscored_predictions(
        self,
        db: AsyncSession,
    ) -> Sequence[Market]:
        """
        Return markets that are resolved (YES or NO) and still have at least
        one prediction with brier_score IS NULL.

        Called by detect_and_score_resolutions() every 5 minutes.
        """
        from data.models.prediction import Prediction

        # Subquery: IDs of markets that have at least one unscored prediction.
        unscored_market_ids = (
            select(Prediction.market_id)
            .where(Prediction.brier_score.is_(None))
            .distinct()
            .scalar_subquery()
        )

        result = await db.execute(
            select(Market).where(
                Market.outcome.isnot(None),
                Market.outcome != MarketOutcome.AMBIGUOUS,
                Market.id.in_(unscored_market_ids),
            )
        )
        return result.scalars().all()


# ---------------------------------------------------------------------------
# Outcome mapping helper (module-level, not a CRUD method)
# ---------------------------------------------------------------------------

def _map_outcome(source: str, raw: str | None) -> Optional[MarketOutcome]:
    """
    Map a platform-specific resolution string to the internal MarketOutcome enum.

    Platform conventions:
      Kalshi    : "yes" | "no"
      Manifold  : "YES" | "NO" | "MKT" | "N/A"
      Metaculus : "yes" | "no" | "annulled" | "ambiguous"
      Polymarket: outcome label ("Yes", "No", or a team/candidate name)
    """
    if not raw:
        return None
    rlow = raw.lower()
    if rlow in ("yes", "true"):
        return MarketOutcome.YES
    if rlow in ("no", "false"):
        return MarketOutcome.NO
    # Manifold MKT (probabilistic resolution), N/A (voided),
    # Metaculus annulled/ambiguous, any other label from Polymarket
    return MarketOutcome.AMBIGUOUS


MarketCRUD = MarketCRUD(Market)
