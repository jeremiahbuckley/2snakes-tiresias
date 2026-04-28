"""
Kalshi → Tiresias adapter.

Converts raw Kalshi API objects into the normalised internal dicts expected
by the data layer. Three separate record types:

  Market     — metadata about a prediction market (question, resolution, etc.)
  Fill       — a user's individual bet execution
  Settlement — resolution outcome for a user's position in a market

API version: openapi-20260415.yaml
  - Base URL changed to api.elections.kalshi.com
  - Fill prices/counts now use fixed-point strings (FixedPointDollars /
    FixedPointCount) instead of integer cents.
  - Settlement timestamp field renamed updated_time → settled_time.
  - Settlement market_result enum extended: yes | no | scalar | void.
  - Market fields title and expiration_time are deprecated; prefer
    yes_sub_title/no_sub_title and latest_expiration_time respectively.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any


def normalise_market(raw: dict[str, Any]) -> dict[str, Any]:
    """
    Map a raw Kalshi market object to the internal Market schema.

    title is deprecated in the new API spec; we prefer it when present but
    fall back to combining yes_sub_title and no_sub_title.

    expiration_time is deprecated; latest_expiration_time is the replacement.
    We read latest_expiration_time first and fall back to expiration_time for
    any cached/legacy responses still using the old field.
    """
    return {
        "external_id": raw.get("ticker"),
        "source": "kalshi",
        "title": _market_title(raw),
        "description": raw.get("rules_primary"),
        "resolution_criteria": raw.get("rules_secondary"),
        "closes_at": _parse_ts(raw.get("close_time")),
        "resolves_at": _parse_ts(
            raw.get("latest_expiration_time") or raw.get("expiration_time")
        ),
        "resolved": raw.get("status") == "finalized",
        "outcome": raw.get("result"),  # "yes" | "no" | None
        "tags": _market_tags(raw),
        "raw": raw,
    }


def normalise_fill(raw: dict[str, Any], user_id: str) -> dict[str, Any]:
    """
    Map a raw Kalshi portfolio fill to the internal Bet schema.

    As of openapi-20260415.yaml, prices and counts are fixed-point strings:
      yes_price_dollars — string decimal in dollars, e.g. "0.62" (range 0.0–1.0)
      count_fp          — string decimal contract count, e.g. "10.0000"

    The primary fill identifier is now fill_id; trade_id is retained by the
    API as a legacy alias and is used as fallback here.

    Backward compat: if a response still carries the old integer fields
    (yes_price in cents, count as int), those are used as fallbacks so that
    any cached responses or staging environments on the old schema still work.

    Currency: Kalshi is CFTC-regulated and denominated in USD.
    """
    return {
        "external_id": raw.get("fill_id") or raw.get("trade_id"),
        "source": "kalshi",
        "user_external_id": user_id,
        "market_external_id": raw.get("ticker") or raw.get("market_ticker"),
        "side": raw.get("side"),                          # "yes" | "no"
        "action": raw.get("action"),                      # "buy" | "sell"
        "count": _parse_count(raw),                       # number of contracts (float)
        "yes_price": _parse_yes_price(raw),               # price as decimal 0.0–1.0
        "currency": "USD",
        "predicted_probability": _yes_probability(raw),
        "placed_at": _parse_ts(raw.get("created_time")),
        "raw": raw,
    }


def normalise_settlement(raw: dict[str, Any], user_id: str) -> dict[str, Any]:
    """
    Map a raw Kalshi portfolio settlement to the internal Settlement schema.

    As of openapi-20260415.yaml:
      - The timestamp field was renamed from updated_time to settled_time.
        We read settled_time first and fall back to updated_time so that any
        cached/legacy responses are still handled correctly.
      - market_result now has four possible values: "yes" | "no" | "scalar" | "void".
        scalar — the market resolved at a specific numeric value (see value field).
        void   — the market was cancelled; positions returned at cost.

    revenue is still an integer in cents (can be negative).
    Currency: USD.
    """
    return {
        "external_id": None,          # no unique settlement ID in the API; data layer uses composite key
        "source": "kalshi",
        "user_external_id": user_id,
        "market_external_id": raw.get("ticker"),
        "market_result": raw.get("market_result"),   # "yes" | "no" | "scalar" | "void"
        "revenue": raw.get("revenue"),               # payout in cents (can be negative)
        "currency": "USD",
        "settled_at": _parse_ts(
            raw.get("settled_time") or raw.get("updated_time")
        ),
        "raw": raw,
    }


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _market_tags(raw: dict[str, Any]) -> list[str]:
    """
    Combine the native tags array with the legacy category field.

    The Kalshi API returns a `tags` list of strings on each market object.
    The `category` field (a single string) is an older field that overlaps
    with tags on some markets. We read both and deduplicate.
    """
    tags: list[str] = list(raw.get("tags") or [])
    category = raw.get("category")
    if category and category not in tags:
        tags.append(category)
    return tags


def _parse_ts(ts: str | None) -> datetime | None:
    if not ts:
        return None
    return datetime.fromisoformat(ts.replace("Z", "+00:00"))


def _market_title(raw: dict[str, Any]) -> str | None:
    """
    Return the best available market title.

    title is deprecated in openapi-20260415.yaml. When it is absent, combine
    yes_sub_title and no_sub_title (e.g. "Yes: X / No: Y") as a fallback.
    """
    if raw.get("title"):
        return raw["title"]
    yes_sub = raw.get("yes_sub_title")
    no_sub = raw.get("no_sub_title")
    if yes_sub and no_sub:
        return f"Yes: {yes_sub} / No: {no_sub}"
    return yes_sub or no_sub or None


def _parse_count(fill: dict[str, Any]) -> float | None:
    """
    Parse contract count from a fill.

    New API: count_fp is a FixedPointCount string, e.g. "10.0000".
    Old API fallback: count is a plain integer.
    """
    count_fp = fill.get("count_fp")
    if count_fp is not None:
        try:
            return float(count_fp)
        except (TypeError, ValueError):
            pass
    count = fill.get("count")
    return float(count) if count is not None else None


def _parse_yes_price(fill: dict[str, Any]) -> float | None:
    """
    Parse the yes-side price from a fill, returning a decimal 0.0–1.0.

    New API: yes_price_dollars is a FixedPointDollars string already in the
    0.0–1.0 range, e.g. "0.62".
    Old API fallback: yes_price is an integer in cents (0–100); divide by 100.
    """
    dollars = fill.get("yes_price_dollars")
    if dollars is not None:
        try:
            return float(dollars)
        except (TypeError, ValueError):
            pass
    cents = fill.get("yes_price")
    return cents / 100.0 if cents is not None else None


def _yes_probability(fill: dict[str, Any]) -> float | None:
    """
    Derive the implied probability that "yes" wins from a fill.

    For a buy-yes or sell-no fill the yes price is the direct probability.
    For a buy-no or sell-yes fill the probability of yes is 1 - no_price.

    In practice Kalshi always provides yes_price_dollars so we use that
    directly; the no_price is 1 - yes_price for a binary market.
    """
    return _parse_yes_price(fill)
