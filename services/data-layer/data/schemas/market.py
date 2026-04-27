"""
Pydantic schemas for Market.
"""

from __future__ import annotations

from datetime import datetime
from typing import Optional
from uuid import UUID

from pydantic import BaseModel, Field, model_validator

from data.models.market import MarketOutcome


# ---------------------------------------------------------------------------
# Write schemas
# ---------------------------------------------------------------------------

class MarketCreate(BaseModel):
    title: str = Field(..., min_length=10, max_length=512)
    description: Optional[str] = Field(None, max_length=10_000)
    resolution_criteria: Optional[str] = Field(None, max_length=5_000)
    tags: list[str] = Field(default_factory=list)
    source_url: Optional[str] = Field(None, max_length=2048)
    closes_at: Optional[datetime] = None
    resolves_at: Optional[datetime] = None

    @model_validator(mode="after")
    def closes_before_resolves(self) -> "MarketCreate":
        if self.closes_at and self.resolves_at:
            if self.closes_at > self.resolves_at:
                raise ValueError("closes_at must be before resolves_at")
        return self


class MarketUpdate(BaseModel):
    title: Optional[str] = Field(None, min_length=10, max_length=512)
    description: Optional[str] = Field(None, max_length=10_000)
    resolution_criteria: Optional[str] = Field(None, max_length=5_000)
    tags: Optional[list[str]] = None
    source_url: Optional[str] = Field(None, max_length=2048)
    closes_at: Optional[datetime] = None
    resolves_at: Optional[datetime] = None


class MarketResolve(BaseModel):
    outcome: MarketOutcome


# ---------------------------------------------------------------------------
# Read schemas
# ---------------------------------------------------------------------------

class MarketPublic(BaseModel):
    id: UUID
    creator_id: Optional[UUID]
    title: str
    description: Optional[str]
    resolution_criteria: Optional[str]
    tags: list[str]
    source_url: Optional[str]
    closes_at: Optional[datetime]
    resolves_at: Optional[datetime]
    resolved_at: Optional[datetime]
    outcome: Optional[MarketOutcome]
    created_at: datetime
    updated_at: datetime

    # Convenience flags
    is_resolved: bool
    is_open: bool

    model_config = {"from_attributes": True}
