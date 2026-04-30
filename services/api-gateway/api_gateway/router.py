"""
Top-level data route handlers for the api-gateway.

These handlers own the HTTP layer: auth, ownership checks, and response.
All query logic lives in data_queries.py for easy future extraction to
a dedicated data microservice.
"""
from __future__ import annotations

from datetime import datetime, timezone, timedelta
from typing import Annotated, Optional
from uuid import UUID

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from auth_service.api import get_current_user
from data.database import db_context, get_db
from data.models.linked_account import LinkedAccount, MARKET_PLATFORMS
from data.models.user import User

from api_gateway.data_queries import (
    get_dashboard_data,
    get_predictions as _get_predictions,
    get_stats_data,
)

async def _background_sync(user_id: UUID) -> None:
    from scheduler.sync import sync_one_user
    async with db_context() as db:
        await sync_one_user(db, user_id)


router = APIRouter()

DB = Annotated[AsyncSession, Depends(get_db)]
CurrentUser = Annotated[User, Depends(get_current_user)]


@router.get("/users/{user_id}/profile")
async def get_user_profile(user_id: str) -> dict:
    return {"user_id": user_id, "status": "stub"}


@router.get("/users/{user_id}/dashboard")
async def get_user_dashboard(
    user_id: str,
    current_user: CurrentUser,
    db: DB,
    tag: Optional[str] = Query(default=None),
) -> dict:
    if user_id != str(current_user.id):
        raise HTTPException(status_code=403)
    return await get_dashboard_data(db, current_user.id, tag=tag)


@router.get("/users/{user_id}/predictions")
async def list_user_predictions(
    user_id: str,
    current_user: CurrentUser,
    db: DB,
    source: Optional[str] = None,
    status: Optional[str] = None,
    sort: Optional[str] = None,
    tag: Optional[str] = Query(default=None),
) -> dict:
    if user_id != str(current_user.id):
        raise HTTPException(status_code=403)
    return await _get_predictions(db, current_user.id, source, status, sort, tag=tag)


@router.get("/users/{user_id}/stats")
async def get_user_stats(
    user_id: str,
    current_user: CurrentUser,
    db: DB,
    tag: Optional[str] = Query(default=None),
) -> dict:
    if user_id != str(current_user.id):
        raise HTTPException(status_code=403)
    return await get_stats_data(db, current_user.id, tag=tag)


@router.get("/leaderboard")
async def get_leaderboard(limit: int = 100, offset: int = 0) -> dict:
    return {"entries": [], "total": 0, "status": "stub"}


@router.get("/markets")
async def list_markets(source: Optional[str] = None, resolved: Optional[bool] = None) -> dict:
    return {"markets": [], "status": "stub"}


@router.post("/users/{user_id}/sync", status_code=202)
async def trigger_user_sync(
    user_id: str,
    background_tasks: BackgroundTasks,
    current_user: CurrentUser,
    db: DB,
) -> dict:
    if user_id != str(current_user.id):
        raise HTTPException(status_code=403)

    rate_limit_cutoff = datetime.now(timezone.utc) - timedelta(seconds=60)
    recent = await db.execute(
        select(LinkedAccount.last_synced_at).where(
            LinkedAccount.user_id == current_user.id,
            LinkedAccount.platform.in_([p.value for p in MARKET_PLATFORMS]),
            LinkedAccount.last_synced_at > rate_limit_cutoff,
        ).limit(1)
    )
    if recent.scalar_one_or_none() is not None:
        raise HTTPException(status_code=429, detail="Sync triggered too recently, please wait")

    background_tasks.add_task(_background_sync, current_user.id)
    return {"status": "syncing"}
