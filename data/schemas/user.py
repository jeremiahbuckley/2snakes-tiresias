"""
Pydantic schemas for User.

UserCreate     — incoming registration payload (includes password)
UserUpdate     — partial profile update (no password field; use auth flow)
UserPublic     — safe to expose to any client (no PII beyond display name)
UserPrivate    — extended view for the authenticated user themselves
"""

from __future__ import annotations

from datetime import datetime
from typing import Optional
from uuid import UUID

from pydantic import BaseModel, EmailStr, Field, HttpUrl, field_validator, model_validator


class _SocialLinks(BaseModel):
    twitter: Optional[str] = None
    manifold: Optional[str] = None
    metaculus: Optional[str] = None
    kalshi: Optional[str] = None
    website: Optional[str] = None

    model_config = {"extra": "allow"}  # allow unknown platforms


# ---------------------------------------------------------------------------
# Write schemas
# ---------------------------------------------------------------------------

class UserCreate(BaseModel):
    email: EmailStr
    username: str = Field(..., min_length=3, max_length=64, pattern=r"^[a-zA-Z0-9_\-]+$")
    password: str = Field(..., min_length=8, max_length=128)
    display_name: Optional[str] = Field(None, max_length=128)

    @field_validator("username")
    @classmethod
    def username_lowercase(cls, v: str) -> str:
        return v.lower()


class UserUpdate(BaseModel):
    display_name: Optional[str] = Field(None, max_length=128)
    bio: Optional[str] = Field(None, max_length=2000)
    avatar_url: Optional[str] = Field(None, max_length=2048)
    social_links: Optional[_SocialLinks] = None


# ---------------------------------------------------------------------------
# Read schemas
# ---------------------------------------------------------------------------

class UserPublic(BaseModel):
    """What the world sees — safe to expose in leaderboards, comment threads, etc."""
    id: UUID
    username: str
    display_name: Optional[str]
    bio: Optional[str]
    avatar_url: Optional[str]
    social_links: Optional[_SocialLinks]
    created_at: datetime

    model_config = {"from_attributes": True}


class UserPrivate(UserPublic):
    """Extended view for the authenticated user themselves."""
    email: str
    is_active: bool
    is_verified: bool
    updated_at: datetime

    model_config = {"from_attributes": True}
