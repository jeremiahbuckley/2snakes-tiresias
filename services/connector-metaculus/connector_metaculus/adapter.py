"""
Metaculus → Tiresias adapter.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any


def normalise_market(raw: dict[str, Any]) -> dict[str, Any]:
    """Map a raw Metaculus question to the internal Market schema."""
    resolution = raw.get("resolution")
    resolved = resolution in (1, 0, -1)  # 1=yes, 0=no, -1=ambiguous

    return {
        "external_id": str(raw.get("id")),
        "source": "metaculus",
        "title": raw.get("title"),
        "description": raw.get("description"),
        "resolution_criteria": raw.get("resolution_criteria"),
        "closes_at": _parse_ts(raw.get("close_time")),
        "resolves_at": _parse_ts(raw.get("resolve_time")),
        "resolved": resolved,
        "outcome": _map_resolution(resolution),
        "raw": raw,
    }


def normalise_prediction(raw_pred: dict[str, Any], user_id: str) -> dict[str, Any]:
    """Map a raw Metaculus prediction to the internal Prediction schema."""
    return {
        "external_id": str(raw_pred.get("id")),
        "source": "metaculus",
        "user_external_id": user_id,
        "market_external_id": str(raw_pred.get("question")),
        "predicted_probability": raw_pred.get("prediction"),  # already 0–1
        "placed_at": _parse_ts(raw_pred.get("t")),
        "raw": raw_pred,
    }


def _parse_ts(ts: str | None) -> datetime | None:
    if not ts:
        return None
    return datetime.fromisoformat(ts.replace("Z", "+00:00"))


def _map_resolution(resolution: int | None) -> str | None:
    return {1: "yes", 0: "no", -1: "ambiguous"}.get(resolution)  # type: ignore[arg-type]
