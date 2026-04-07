"""
Pydantic schemas for UserScore (leaderboard / stats).
"""

from __future__ import annotations

from datetime import datetime
from typing import Optional
from uuid import UUID

from pydantic import BaseModel, computed_field


class UserScorePublic(BaseModel):
    user_id: UUID
    total_predictions: int
    resolved_predictions: int
    mean_brier_score: Optional[float]
    calibration_score: Optional[float]
    accuracy: Optional[float]
    last_scored_at: Optional[datetime]

    @computed_field  # type: ignore[misc]
    @property
    def resolution_rate(self) -> Optional[float]:
        if self.total_predictions == 0:
            return None
        return round(self.resolved_predictions / self.total_predictions, 4)

    model_config = {"from_attributes": True}


class LeaderboardEntry(BaseModel):
    """Leaderboard row — score combined with public user info."""
    rank: int
    user_id: UUID
    username: str
    display_name: Optional[str]
    avatar_url: Optional[str]
    total_predictions: int
    resolved_predictions: int
    mean_brier_score: Optional[float]
    calibration_score: Optional[float]
    accuracy: Optional[float]

    model_config = {"from_attributes": True}
