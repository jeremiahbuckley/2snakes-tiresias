"""
Polymarket → Tiresias adapter.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any


def normalise_market(raw: dict[str, Any]) -> dict[str, Any]:
    """Map a raw Polymarket (Gamma) market to the internal Market schema."""
    # TODO: handle multi-outcome markets (more than binary yes/no)
    return {
        "external_id": raw.get("condition_id"),
        "source": "polymarket",
        "title": raw.get("question"),
        "description": raw.get("description"),
        "resolution_criteria": raw.get("resolution_source"),
        "closes_at": _parse_ts(raw.get("end_date_iso")),
        "resolves_at": _parse_ts(raw.get("end_date_iso")),
        "resolved": raw.get("closed", False),
        "outcome": raw.get("winning_side"),  # "yes" | "no" | None
        "raw": raw,
    }


def normalise_prediction(raw_trade: dict[str, Any], user_id: str) -> dict[str, Any]:
    """Map a raw CLOB trade to the internal Prediction schema."""
    return {
        "external_id": raw_trade.get("id"),
        "source": "polymarket",
        "user_external_id": user_id,
        "market_external_id": raw_trade.get("market"),
        "predicted_probability": _outcome_price(raw_trade),
        "placed_at": _parse_ts(raw_trade.get("created_at")),
        "raw": raw_trade,
    }


def _parse_ts(ts: str | None) -> datetime | None:
    if not ts:
        return None
    return datetime.fromisoformat(ts.replace("Z", "+00:00"))


def _outcome_price(trade: dict[str, Any]) -> float | None:
    """Price in USDC cents → probability (0–1)."""
    price = trade.get("price")
    if price is None:
        return None
    return float(price)
