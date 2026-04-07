"""
Manifold Markets → Tiresias adapter.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any


def normalise_market(raw: dict[str, Any]) -> dict[str, Any]:
    """Map a raw Manifold market to the internal Market schema."""
    # Manifold supports BINARY, FREE_RESPONSE, MULTIPLE_CHOICE, NUMERIC
    # For now we only handle BINARY; others are TODO
    mechanism = raw.get("mechanism", "")
    if mechanism != "cpmm-1":
        pass  # TODO: handle non-binary markets

    return {
        "external_id": raw.get("id"),
        "source": "manifold",
        "title": raw.get("question"),
        "description": raw.get("description"),
        "resolution_criteria": raw.get("resolutionCriteria"),
        "closes_at": _parse_ms(raw.get("closeTime")),
        "resolves_at": _parse_ms(raw.get("resolutionTime")),
        "resolved": raw.get("isResolved", False),
        "outcome": raw.get("resolution"),  # "YES" | "NO" | "N/A" | None
        "raw": raw,
    }


def normalise_prediction(raw_bet: dict[str, Any], user_id: str) -> dict[str, Any]:
    """Map a raw Manifold bet to the internal Prediction schema."""
    return {
        "external_id": raw_bet.get("id"),
        "source": "manifold",
        "user_external_id": user_id,
        "market_external_id": raw_bet.get("contractId"),
        "predicted_probability": raw_bet.get("probAfter"),
        "placed_at": _parse_ms(raw_bet.get("createdTime")),
        "raw": raw_bet,
    }


def _parse_ms(ts_ms: int | None) -> datetime | None:
    """Manifold uses millisecond Unix timestamps."""
    if ts_ms is None:
        return None
    return datetime.fromtimestamp(ts_ms / 1000, tz=timezone.utc)
