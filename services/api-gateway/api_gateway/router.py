"""
Top-level data route handlers for the api-gateway.

These handlers own the HTTP layer: auth, ownership checks, and response.
All query logic lives in data_queries.py for easy future extraction to
a dedicated data microservice.
"""
from __future__ import annotations

from typing import Annotated, Optional

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from auth_service.api import get_current_user
from data.database import get_db
from data.models.user import User

from api_gateway.data_queries import (
    get_dashboard_data,
    get_predictions as _get_predictions,
    get_stats_data,
)

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
) -> dict:
    if user_id != str(current_user.id):
        raise HTTPException(status_code=403)
    return await get_dashboard_data(db, current_user.id)


@router.get("/users/{user_id}/predictions")
async def list_user_predictions(
    user_id: str,
    current_user: CurrentUser,
    db: DB,
    source: Optional[str] = None,
    status: Optional[str] = None,
    sort: Optional[str] = None,
) -> dict:
    if user_id != str(current_user.id):
        raise HTTPException(status_code=403)
    return await _get_predictions(db, current_user.id, source, status, sort)


@router.get("/users/{user_id}/stats")
async def get_user_stats(
    user_id: str,
    current_user: CurrentUser,
    db: DB,
) -> dict:
    if user_id != str(current_user.id):
        raise HTTPException(status_code=403)
    return await get_stats_data(db, current_user.id)


@router.get("/leaderboard")
async def get_leaderboard(limit: int = 100, offset: int = 0) -> dict:
    return {"entries": [], "total": 0, "status": "stub"}


@router.get("/markets")
async def list_markets(source: Optional[str] = None, resolved: Optional[bool] = None) -> dict:
    return {"markets": [], "status": "stub"}
