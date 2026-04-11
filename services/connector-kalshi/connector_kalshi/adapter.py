"""
Kalshi → Tiresias adapter.

Converts raw Kalshi API objects into the normalised internal dicts expected
by the data layer. Three separate record types:

  Market     — metadata about a prediction market (question, resolution, etc.)
  Fill       — a user's individual bet execution
  Settlement — resolution outcome for a user's position in a market
"""

from __future__ import annotations

from datetime import datetime
from typing import Any


def normalise_market(raw: dict[str, Any]) -> dict[str, Any]:
    """Map a raw Kalshi market object to the internal Market schema."""
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


def normalise_fill(raw: dict[str, Any], user_id: str) -> dict[str, Any]:
    """
    Map a raw Kalshi portfolio fill to the internal Bet schema.

    A fill is one execution of an order — the user bought or sold contracts
    in a market at a specific price. yes_price is in cents (0–100).
    """
    return {
        "external_id": raw.get("trade_id"),
        "source": "kalshi",
        "user_external_id": user_id,
        "market_external_id": raw.get("ticker"),
        "side": raw.get("side"),                      # "yes" | "no"
        "action": raw.get("action"),                  # "buy" | "sell"
        "count": raw.get("count"),                    # number of contracts
        "yes_price": raw.get("yes_price"),            # price paid in cents (0–100)
        "predicted_probability": _yes_probability(raw),
        "placed_at": _parse_ts(raw.get("created_time")),
        "raw": raw,
    }


def normalise_settlement(raw: dict[str, Any], user_id: str) -> dict[str, Any]:
    """
    Map a raw Kalshi portfolio settlement to the internal Settlement schema.

    A settlement is the final payout event when a market resolves.
    revenue is in cents.
    """
    return {
        "external_id": raw.get("market_result"),      # no unique ID; use composite key in data layer
        "source": "kalshi",
        "user_external_id": user_id,
        "market_external_id": raw.get("ticker"),
        "market_result": raw.get("market_result"),    # "yes" | "no"
        "revenue": raw.get("revenue"),                # payout in cents (can be negative)
        "settled_at": _parse_ts(raw.get("updated_time")),
        "raw": raw,
    }


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _parse_ts(ts: str | None) -> datetime | None:
    if not ts:
        return None
    return datetime.fromisoformat(ts.replace("Z", "+00:00"))


def _yes_probability(fill: dict[str, Any]) -> float | None:
    """Convert yes_price (0–100 cents) to a probability (0.0–1.0)."""
    yes_price = fill.get("yes_price")
    if yes_price is None:
        return None
    return yes_price / 100.0
