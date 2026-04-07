"""
Kalshi → Tiresias adapter.

Converts raw Kalshi API objects into the normalised internal dicts expected
by the data layer (Market, Prediction).
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any


def normalise_market(raw: dict[str, Any]) -> dict[str, Any]:
    """
    Map a raw Kalshi market object to the internal Market schema.

    TODO: map all relevant fields; add resolution logic.
    """
    return {
        "external_id": raw.get("ticker"),
        "source": "kalshi",
        "title": raw.get("title"),
        "description": raw.get("rules_primary"),
        "resolution_criteria": raw.get("rules_secondary"),
        "closes_at": _parse_ts(raw.get("close_time")),
        "resolves_at": _parse_ts(raw.get("expiration_time")),
        "resolved": raw.get("status") == "finalized",
        "outcome": raw.get("result"),  # "yes" | "no" | None
        "raw": raw,
    }


def normalise_prediction(raw_trade: dict[str, Any], user_id: str) -> dict[str, Any]:
    """
    Map a raw Kalshi trade to the internal Prediction schema.

    TODO: handle multi-leg trades; map count → probability.
    """
    return {
        "external_id": raw_trade.get("trade_id"),
        "source": "kalshi",
        "user_external_id": user_id,
        "market_external_id": raw_trade.get("ticker"),
        "predicted_probability": _yes_probability(raw_trade),
        "placed_at": _parse_ts(raw_trade.get("created_time")),
        "raw": raw_trade,
    }


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _parse_ts(ts: str | None) -> datetime | None:
    if not ts:
        return None
    return datetime.fromisoformat(ts.replace("Z", "+00:00"))


def _yes_probability(trade: dict[str, Any]) -> float | None:
    """Approximate yes-probability from a Kalshi trade's yes_price (0-100 cents)."""
    yes_price = trade.get("yes_price")
    if yes_price is None:
        return None
    return yes_price / 100.0
