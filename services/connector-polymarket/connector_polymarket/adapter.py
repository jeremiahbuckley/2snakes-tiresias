"""
Polymarket → Tiresias adapter.

Converts raw Polymarket API objects into the normalised internal dicts expected
by the data layer. Three separate record types:

  Market          — metadata about a prediction market (from Gamma API)
  Trade           — a user's individual trade execution (from Data API /trades)
  ClosedPosition  — resolved position outcome and P&L (from Data API /closed-positions)

Notes on Polymarket data quirks:
  - Market `outcomes` and `outcomePrices` fields are JSON-encoded strings, not arrays.
    e.g. outcomes = '["Yes", "No"]' — must be parsed with json.loads().
  - Market `conditionId` (0x-prefixed 64-hex) is the stable cross-platform identifier.
    The Gamma integer `id` is only used for Gamma API lookups.
  - Trade `price` is already in 0.0–1.0 range (USDC per share), not cents.
  - Trade `timestamp` is a Unix integer (seconds).
  - Closed position `realizedPnl` is in USDC.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Any


def normalise_market(raw: dict[str, Any]) -> dict[str, Any]:
    """
    Map a raw Polymarket Gamma market object to the internal Market schema.

    The `closed` field indicates resolution. Outcome is derived from
    `outcomePrices` — the winning outcome has a price of "1" (or "1.0").
    For binary markets this maps cleanly; multi-outcome markets (TODO) need
    special handling.
    """
    outcomes = _parse_json_str(raw.get("outcomes"))
    outcome_prices = _parse_json_str(raw.get("outcomePrices"))
    resolved_outcome = _winning_outcome(outcomes, outcome_prices)

    return {
        "external_id": raw.get("conditionId"),
        "source": "polymarket",
        "title": raw.get("question"),
        "description": raw.get("description"),
        "resolution_criteria": raw.get("resolutionSource"),
        "closes_at": _parse_ts(raw.get("endDateIso") or raw.get("endDate")),
        "resolves_at": _parse_ts(raw.get("endDateIso") or raw.get("endDate")),
        "resolved": raw.get("closed", False),
        "outcome": resolved_outcome,
        "tags": [t.get("slug") for t in (raw.get("tags") or []) if t.get("slug")],
        "raw": raw,
    }


def normalise_trade(raw: dict[str, Any], user_id: str) -> dict[str, Any]:
    """
    Map a raw Data API trade to the internal Bet schema.

    Each trade is one execution — the user bought or sold shares of a specific
    outcome token at a given price. Price is 0.0–1.0 (USDC per share).
    """
    return {
        "external_id": raw.get("transactionHash"),  # most stable unique ID
        "source": "polymarket",
        "user_external_id": user_id,
        "market_external_id": raw.get("conditionId"),
        "side": raw.get("side"),               # "BUY" | "SELL"
        "outcome": raw.get("outcome"),          # e.g. "Yes" | "No" | team name etc.
        "outcome_index": raw.get("outcomeIndex"),
        "size": raw.get("size"),                # number of shares
        "price": raw.get("price"),              # 0.0–1.0
        "predicted_probability": _trade_probability(raw),
        "placed_at": _parse_unix_ts(raw.get("timestamp")),
        "slug": raw.get("slug"),                # retained for market lookup
        "raw": raw,
    }


def normalise_closed_position(raw: dict[str, Any], user_id: str) -> dict[str, Any]:
    """
    Map a raw Data API closed position to the internal ClosedPosition schema.

    A closed position is the aggregate outcome for a user's entire position in
    a market after it resolves — equivalent to Kalshi's settlement record.
    realizedPnl is in USDC (can be negative).
    """
    return {
        "external_id": raw.get("conditionId"),   # one record per market per user
        "source": "polymarket",
        "user_external_id": user_id,
        "market_external_id": raw.get("conditionId"),
        "outcome": raw.get("outcome"),            # which side the user held
        "outcome_index": raw.get("outcomeIndex"),
        "avg_price": raw.get("avgPrice"),         # average entry price (0.0–1.0)
        "total_bought": raw.get("totalBought"),   # total USDC spent
        "realized_pnl": raw.get("realizedPnl"),   # net profit/loss in USDC
        "closed_at": _parse_ts(raw.get("endDate")),
        "slug": raw.get("slug"),                  # retained for market lookup
        "raw": raw,
    }


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _parse_ts(ts: str | None) -> datetime | None:
    """Parse an ISO 8601 timestamp string."""
    if not ts:
        return None
    try:
        return datetime.fromisoformat(ts.replace("Z", "+00:00"))
    except ValueError:
        return None


def _parse_unix_ts(ts: int | None) -> datetime | None:
    """Parse a Unix integer timestamp (seconds)."""
    if ts is None:
        return None
    return datetime.fromtimestamp(ts, tz=timezone.utc)


def _parse_json_str(value: str | None) -> list | None:
    """Polymarket encodes outcomes/outcomePrices as JSON strings within JSON."""
    if not value:
        return None
    try:
        return json.loads(value)
    except (json.JSONDecodeError, TypeError):
        return None


def _winning_outcome(outcomes: list | None, prices: list | None) -> str | None:
    """
    Determine the winning outcome from outcomePrices.

    The winning outcome has a final price of 1.0 (or "1"). Returns the
    outcome label string, or None if the market is unresolved or data is missing.
    TODO: multi-outcome markets may have more complex resolution logic.
    """
    if not outcomes or not prices:
        return None
    for label, price in zip(outcomes, prices):
        try:
            if float(price) == 1.0:
                return str(label)
        except (ValueError, TypeError):
            continue
    return None


def _trade_probability(trade: dict[str, Any]) -> float | None:
    """
    Interpret trade price as a probability.

    For a BUY of a YES token at price 0.65, predicted_probability = 0.65.
    For a BUY of a NO token at price 0.35, predicted_probability = 1 - 0.35 = 0.65.
    For a SELL, the probability interpretation is ambiguous — return raw price.
    TODO: refine once we validate against real trade data.
    """
    price = trade.get("price")
    if price is None:
        return None
    price = float(price)
    outcome = (trade.get("outcome") or "").lower()
    side = (trade.get("side") or "").upper()
    if side == "BUY" and outcome in ("no", "false"):
        return 1.0 - price
    return price
