"""
Badge service FastAPI router.

Mounts at /badges — intended to be included in the api-gateway.
"""

from __future__ import annotations

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

router = APIRouter(prefix="/badges", tags=["badges"])


class BadgeOut(BaseModel):
    id: str
    name: str
    description: str


class UserBadgesOut(BaseModel):
    user_id: str
    badges: list[BadgeOut]


@router.get("/", response_model=list[BadgeOut])
async def list_badges() -> list[BadgeOut]:
    """Return all available badge definitions."""
    from .badges import BADGES
    return [BadgeOut(id=b.id, name=b.name, description=b.description) for b in BADGES]


@router.get("/user/{user_id}", response_model=UserBadgesOut)
async def get_user_badges(user_id: str) -> UserBadgesOut:
    """Return the badges earned by a specific user."""
    # TODO: fetch from DB via data layer
    raise HTTPException(status_code=501, detail="Not yet implemented")
