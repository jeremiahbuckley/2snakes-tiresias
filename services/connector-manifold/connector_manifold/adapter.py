"""
Manifold Markets → Tiresias adapter.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any


def normalise_market(raw: dict[str, Any]) -> dict[str, Any]:
    """Map a raw Manifold FullMarket to the internal Market schema.

    Notable Manifold quirks:
    - `description` is a TipTap JSONContent blob; use `textDescription` for plain text.
    - `resolution` is "YES" | "NO" | "MKT" | "N/A" for BINARY markets (or None if open).
    - `groupSlugs` carries the topic tags (string list).
    - Timestamps are millisecond Unix integers.
    """
    return {
        "external_id": raw.get("id"),
        "source": "manifold",
        "title": raw.get("question"),
        "description": raw.get("textDescription"),       # plain text, not TipTap JSON
        "resolution_criteria": raw.get("resolutionCriteria"),
        "closes_at": _parse_ms(raw.get("closeTime")),
        "resolves_at": _parse_ms(raw.get("resolutionTime")),
        "resolved": raw.get("isResolved", False),
        "outcome": raw.get("resolution"),               # "YES" | "NO" | "MKT" | "N/A" | None
        "tags": raw.get("groupSlugs", []),
        "raw": raw,
    }


def normalise_bet(raw_bet: dict[str, Any], user_id: str) -> dict[str, Any]:
    """Map a raw Manifold bet to the internal Prediction schema.

    Key fields:
    - `outcome`  : "YES" or "NO" — which side the user bet on.
    - `amount`   : mana spent (positive = buy, negative = sale).
    - `probBefore`: market probability immediately before this bet.
    - `probAfter` : market probability immediately after this bet.
    - `predicted_probability`: we use probBefore — the market's stated price
      when the user decided to place their bet, analogous to the fill price on
      other platforms.

    Caller should filter out `isRedemption == True` bets before storing; those
    are automated resolution events, not user decisions.
    """
    outcome = raw_bet.get("outcome")          # "YES" | "NO"
    prob_before = raw_bet.get("probBefore")   # probability *before* the bet
    prob_after = raw_bet.get("probAfter")     # probability *after* the bet

    # Derive a normalised predicted probability relative to YES.
    # For a YES bet, probBefore is the price the user accepted.
    # For a NO bet, the implied YES probability is (1 - probBefore).
    if prob_before is not None:
        if outcome == "NO":
            predicted_probability = 1.0 - prob_before
        else:
            predicted_probability = prob_before
    else:
        predicted_probability = None

    return {
        "external_id": raw_bet.get("id"),
        "source": "manifold",
        "user_external_id": user_id,
        "market_external_id": raw_bet.get("contractId"),
        "outcome": outcome,
        "amount": raw_bet.get("amount"),          # mana (positive = buy)
        "shares": raw_bet.get("shares"),
        "currency": "MANA",                       # Manifold play-money; not convertible to USD
        "prob_before": prob_before,
        "prob_after": prob_after,
        "predicted_probability": predicted_probability,
        "placed_at": _parse_ms(raw_bet.get("createdTime")),
        "is_redemption": raw_bet.get("isRedemption", False),
        "raw": raw_bet,
    }


def _parse_ms(ts_ms: int | None) -> datetime | None:
    """Manifold uses millisecond Unix timestamps."""
    if ts_ms is None:
        return None
    return datetime.fromtimestamp(ts_ms / 1000, tz=timezone.utc)
