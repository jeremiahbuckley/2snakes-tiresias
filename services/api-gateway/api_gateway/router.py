"""
Top-level route stubs.

These will be replaced by real implementations as each service matures.
"""

from __future__ import annotations

from fastapi import APIRouter

router = APIRouter()


@router.get("/users/{user_id}/profile")
async def get_user_profile(user_id: str) -> dict:
    """Public profile for a user — predictions, scores, badges."""
    # TODO: aggregate from data layer + badge-service
    return {"user_id": user_id, "status": "stub"}


@router.get("/users/{user_id}/dashboard")
async def get_user_dashboard(user_id: str) -> dict:
    """Private dashboard data — full history, detailed stats."""
    # TODO: auth required; return richer data than public profile
    return {"user_id": user_id, "status": "stub"}


@router.get("/leaderboard")
async def get_leaderboard(limit: int = 100, offset: int = 0) -> dict:
    """Paginated public leaderboard."""
    # TODO: read from leaderboard snapshot table
    return {"entries": [], "total": 0, "status": "stub"}


@router.get("/markets")
async def list_markets(source: str | None = None, resolved: bool | None = None) -> dict:
    """List markets, optionally filtered by source or resolution status."""
    # TODO: query data layer
    return {"markets": [], "status": "stub"}
