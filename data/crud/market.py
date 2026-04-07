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
        category: Optional[str] = None,
    ) -> Sequence[Market]:
        """Return markets that are not yet resolved."""
        stmt = (
            select(Market)
            .where(Market.outcome.is_(None))
            .offset(skip)
            .limit(limit)
            .order_by(Market.created_at.desc())
        )
        if category:
            stmt = stmt.where(Market.category == category)
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


MarketCRUD = MarketCRUD(Market)
