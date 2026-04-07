"""
Pydantic schemas for Prediction.
"""

from __future__ import annotations

from datetime import datetime
from typing import Optional
from uuid import UUID

from pydantic import BaseModel, Field, field_validator


# ---------------------------------------------------------------------------
# Write schemas
# ---------------------------------------------------------------------------

class PredictionCreate(BaseModel):
    market_id: UUID
    probability: float = Field(..., ge=0.0, le=1.0)
    rationale: Optional[str] = Field(None, max_length=5_000)

    @field_validator("probability")
    @classmethod
    def round_probability(cls, v: float) -> float:
        # Store at most 5 decimal places
        return round(v, 5)


class PredictionUpdate(BaseModel):
    """Only the rationale can be updated post-creation; probability is immutable."""
    rationale: Optional[str] = Field(None, max_length=5_000)


# ---------------------------------------------------------------------------
# Read schemas
# ---------------------------------------------------------------------------

class PredictionPublic(BaseModel):
    id: UUID
    user_id: UUID
    market_id: UUID
    probability: float
    rationale: Optional[str]
    resolved_at: Optional[datetime]
    brier_score: Optional[float]
    created_at: datetime
    updated_at: datetime
    is_resolved: bool

    model_config = {"from_attributes": True}
