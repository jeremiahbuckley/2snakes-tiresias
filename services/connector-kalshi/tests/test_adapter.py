"""
Unit tests for the Kalshi adapter.

These tests use only static fixture data — no network calls.

Fixtures reflect the openapi-20260415.yaml schema:
  - Fills use count_fp (FixedPointCount string) and yes_price_dollars
    (FixedPointDollars string) instead of integer cents.
  - Settlements use settled_time instead of updated_time.
  - market_result enum extended to include "scalar" and "void".
  - Markets use latest_expiration_time instead of expiration_time.
"""

import pytest
from connector_kalshi.adapter import normalise_fill, normalise_market, normalise_settlement


# ---------------------------------------------------------------------------
# Fixtures — new API format (openapi-20260415.yaml)
# ---------------------------------------------------------------------------

SAMPLE_MARKET = {
    "ticker": "PRES-2024-DEM",
    "yes_sub_title": "Democratic candidate wins",
    "no_sub_title": "Republican or other candidate wins",
    "title": "Will the Democratic candidate win the 2024 US Presidential Election?",  # deprecated
    "rules_primary": "Resolves YES if the Democratic candidate wins.",
    "rules_secondary": None,
    "close_time": "2024-11-05T23:00:00Z",
    "latest_expiration_time": "2024-11-06T12:00:00Z",   # replaces expiration_time
    "expiration_time": "2024-11-06T12:00:00Z",           # deprecated, kept for compat
    "status": "finalized",
    "result": "no",
}

SAMPLE_FILL = {
    "fill_id": "fill-xyz-456",          # new primary ID
    "trade_id": "trade-abc-123",        # legacy alias
    "order_id": "order-def-789",
    "ticker": "PRES-2024-DEM",
    "market_ticker": "PRES-2024-DEM",
    "side": "yes",
    "action": "buy",
    "count_fp": "10.0000",              # FixedPointCount string
    "yes_price_dollars": "0.62",        # FixedPointDollars string (0.0–1.0)
    "no_price_dollars": "0.38",
    "is_taker": True,
    "fee_cost": "0.0100",
    "created_time": "2024-10-01T10:00:00Z",
}

SAMPLE_SETTLEMENT = {
    "ticker": "PRES-2024-DEM",
    "event_ticker": "PRES-2024",
    "market_result": "no",
    "revenue": -620,                    # still integer cents
    "settled_time": "2024-11-06T14:00:00Z",  # renamed from updated_time
    "value": None,
    "fee_cost": "0.0000",
}


# ---------------------------------------------------------------------------
# normalise_market
# ---------------------------------------------------------------------------

def test_normalise_market_fields():
    m = normalise_market(SAMPLE_MARKET)
    assert m["external_id"] == "PRES-2024-DEM"
    assert m["source"] == "kalshi"
    assert m["title"] == "Will the Democratic candidate win the 2024 US Presidential Election?"
    assert m["resolved"] is True
    assert m["outcome"] == "no"


def test_normalise_market_timestamps():
    m = normalise_market(SAMPLE_MARKET)
    assert m["closes_at"] is not None
    assert m["resolves_at"] is not None


def test_normalise_market_uses_latest_expiration_time():
    """latest_expiration_time should be used when present."""
    raw = {**SAMPLE_MARKET, "latest_expiration_time": "2024-12-01T00:00:00Z"}
    m = normalise_market(raw)
    assert m["resolves_at"].year == 2024
    assert m["resolves_at"].month == 12


def test_normalise_market_falls_back_to_expiration_time():
    """Old responses without latest_expiration_time should still parse."""
    raw = {k: v for k, v in SAMPLE_MARKET.items() if k != "latest_expiration_time"}
    m = normalise_market(raw)
    assert m["resolves_at"] is not None


def test_normalise_market_unresolved():
    raw = {**SAMPLE_MARKET, "status": "open", "result": None}
    m = normalise_market(raw)
    assert m["resolved"] is False
    assert m["outcome"] is None


def test_normalise_market_title_fallback_to_sub_titles():
    """When title is absent, combine yes_sub_title and no_sub_title."""
    raw = {k: v for k, v in SAMPLE_MARKET.items() if k != "title"}
    m = normalise_market(raw)
    assert "Democratic candidate wins" in m["title"]
    assert "Republican or other candidate wins" in m["title"]


def test_normalise_market_title_only_yes_sub():
    """Only yes_sub_title available — use it alone."""
    raw = {**SAMPLE_MARKET, "title": None, "no_sub_title": None}
    m = normalise_market(raw)
    assert m["title"] == "Democratic candidate wins"


def test_normalise_market_no_title_at_all():
    raw = {**SAMPLE_MARKET, "title": None, "yes_sub_title": None, "no_sub_title": None}
    m = normalise_market(raw)
    assert m["title"] is None


# ---------------------------------------------------------------------------
# normalise_fill
# ---------------------------------------------------------------------------

def test_normalise_fill_probability():
    f = normalise_fill(SAMPLE_FILL, user_id="user-1")
    assert f["predicted_probability"] == pytest.approx(0.62)


def test_normalise_fill_fields():
    f = normalise_fill(SAMPLE_FILL, user_id="user-1")
    assert f["source"] == "kalshi"
    assert f["user_external_id"] == "user-1"
    assert f["market_external_id"] == "PRES-2024-DEM"
    assert f["side"] == "yes"
    assert f["action"] == "buy"
    assert f["currency"] == "USD"


def test_normalise_fill_uses_fill_id_as_primary():
    """fill_id should be used as external_id when present."""
    f = normalise_fill(SAMPLE_FILL, user_id="user-1")
    assert f["external_id"] == "fill-xyz-456"


def test_normalise_fill_falls_back_to_trade_id():
    """When fill_id is absent, fall back to trade_id (legacy responses)."""
    raw = {k: v for k, v in SAMPLE_FILL.items() if k != "fill_id"}
    f = normalise_fill(raw, user_id="user-1")
    assert f["external_id"] == "trade-abc-123"


def test_normalise_fill_count_fp_parsed_as_float():
    f = normalise_fill(SAMPLE_FILL, user_id="user-1")
    assert f["count"] == pytest.approx(10.0)


def test_normalise_fill_count_legacy_int_fallback():
    """Old responses with integer count field should still work."""
    raw = {k: v for k, v in SAMPLE_FILL.items() if k != "count_fp"}
    raw["count"] = 10
    f = normalise_fill(raw, user_id="user-1")
    assert f["count"] == pytest.approx(10.0)


def test_normalise_fill_yes_price_parsed_as_decimal():
    f = normalise_fill(SAMPLE_FILL, user_id="user-1")
    assert f["yes_price"] == pytest.approx(0.62)


def test_normalise_fill_yes_price_legacy_cents_fallback():
    """Old responses with yes_price in cents (0–100) should still work."""
    raw = {k: v for k, v in SAMPLE_FILL.items() if k != "yes_price_dollars"}
    raw["yes_price"] = 62
    f = normalise_fill(raw, user_id="user-1")
    assert f["yes_price"] == pytest.approx(0.62)
    assert f["predicted_probability"] == pytest.approx(0.62)


def test_normalise_fill_missing_price():
    raw = {k: v for k, v in SAMPLE_FILL.items()
           if k not in ("yes_price_dollars", "yes_price")}
    f = normalise_fill(raw, user_id="user-1")
    assert f["predicted_probability"] is None
    assert f["yes_price"] is None


def test_normalise_fill_timestamp():
    f = normalise_fill(SAMPLE_FILL, user_id="user-1")
    assert f["placed_at"] is not None


def test_normalise_fill_market_ticker_fallback():
    """market_ticker field used when ticker is absent."""
    raw = {k: v for k, v in SAMPLE_FILL.items() if k != "ticker"}
    f = normalise_fill(raw, user_id="user-1")
    assert f["market_external_id"] == "PRES-2024-DEM"


# ---------------------------------------------------------------------------
# normalise_settlement
# ---------------------------------------------------------------------------

def test_normalise_settlement_fields():
    s = normalise_settlement(SAMPLE_SETTLEMENT, user_id="user-1")
    assert s["source"] == "kalshi"
    assert s["market_external_id"] == "PRES-2024-DEM"
    assert s["user_external_id"] == "user-1"
    assert s["market_result"] == "no"
    assert s["revenue"] == -620
    assert s["currency"] == "USD"


def test_normalise_settlement_uses_settled_time():
    s = normalise_settlement(SAMPLE_SETTLEMENT, user_id="user-1")
    assert s["settled_at"] is not None
    assert s["settled_at"].year == 2024
    assert s["settled_at"].month == 11
    assert s["settled_at"].day == 6


def test_normalise_settlement_falls_back_to_updated_time():
    """Old responses using updated_time should still parse correctly."""
    raw = {k: v for k, v in SAMPLE_SETTLEMENT.items() if k != "settled_time"}
    raw["updated_time"] = "2024-11-06T14:00:00Z"
    s = normalise_settlement(raw, user_id="user-1")
    assert s["settled_at"] is not None


def test_normalise_settlement_missing_time():
    raw = {k: v for k, v in SAMPLE_SETTLEMENT.items()
           if k not in ("settled_time", "updated_time")}
    s = normalise_settlement(raw, user_id="user-1")
    assert s["settled_at"] is None


def test_normalise_settlement_scalar_result():
    """scalar market_result should be passed through unchanged."""
    raw = {**SAMPLE_SETTLEMENT, "market_result": "scalar", "value": 42, "revenue": 420}
    s = normalise_settlement(raw, user_id="user-1")
    assert s["market_result"] == "scalar"
    assert s["revenue"] == 420


def test_normalise_settlement_void_result():
    """void market_result (cancelled market) should be passed through unchanged."""
    raw = {**SAMPLE_SETTLEMENT, "market_result": "void", "revenue": 0}
    s = normalise_settlement(raw, user_id="user-1")
    assert s["market_result"] == "void"
    assert s["revenue"] == 0


def test_normalise_settlement_yes_result():
    raw = {**SAMPLE_SETTLEMENT, "market_result": "yes", "revenue": 380}
    s = normalise_settlement(raw, user_id="user-1")
    assert s["market_result"] == "yes"
    assert s["revenue"] == 380


def test_normalise_market_tags_from_tags_array():
    """Native tags array is used when present."""
    raw = {**SAMPLE_MARKET, "tags": ["politics", "us-election"]}
    m = normalise_market(raw)
    assert m["tags"] == ["politics", "us-election"]


def test_normalise_market_tags_from_category():
    """A market with only a category field produces a one-element tags list."""
    raw = {**SAMPLE_MARKET, "category": "Politics"}
    m = normalise_market(raw)
    assert m["tags"] == ["Politics"]


def test_normalise_market_tags_merges_tags_array_and_category():
    """When both tags array and category are present, they are merged without duplicates."""
    raw = {**SAMPLE_MARKET, "tags": ["politics", "us-election"], "category": "sports"}
    m = normalise_market(raw)
    assert "politics" in m["tags"]
    assert "us-election" in m["tags"]
    assert "sports" in m["tags"]
    assert len(m["tags"]) == 3


def test_normalise_market_tags_no_duplicate_when_category_in_tags():
    """category is not added again when it already appears in the tags array."""
    raw = {**SAMPLE_MARKET, "tags": ["Politics", "us-election"], "category": "Politics"}
    m = normalise_market(raw)
    assert m["tags"].count("Politics") == 1


def test_normalise_market_tags_empty_when_no_category_and_no_tags():
    """A market with neither tags nor category produces an empty tags list."""
    raw = {k: v for k, v in SAMPLE_MARKET.items() if k not in ("category", "tags")}
    m = normalise_market(raw)
    assert m["tags"] == []


def test_normalise_market_tags_from_series():
    """Series category and tags are used when the market object has neither."""
    raw = {k: v for k, v in SAMPLE_MARKET.items() if k not in ("category", "tags")}
    series = {"category": "Climate and Weather", "tags": ["Daily temperature"]}
    m = normalise_market(raw, series=series)
    assert "Climate and Weather" in m["tags"]
    assert "Daily temperature" in m["tags"]


def test_normalise_market_tags_series_deduplicates():
    """Series category is not added twice if already present in market tags."""
    raw = {**SAMPLE_MARKET, "tags": ["Climate and Weather"]}
    series = {"category": "Climate and Weather", "tags": ["Daily temperature"]}
    m = normalise_market(raw, series=series)
    assert m["tags"].count("Climate and Weather") == 1
    assert "Daily temperature" in m["tags"]


def test_normalise_market_tags_no_series():
    """Passing series=None is safe — falls back to market-only tags."""
    raw = {**SAMPLE_MARKET, "tags": ["politics"]}
    m = normalise_market(raw, series=None)
    assert m["tags"] == ["politics"]
