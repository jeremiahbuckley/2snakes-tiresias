"""
Unit tests for the Kalshi adapter.

These tests use only static fixture data — no network calls.
"""

import pytest
from connector_kalshi.adapter import normalise_fill, normalise_market, normalise_settlement


SAMPLE_MARKET = {
    "ticker": "PRES-2024-DEM",
    "title": "Will the Democratic candidate win the 2024 US Presidential Election?",
    "rules_primary": "Resolves YES if the Democratic candidate wins.",
    "rules_secondary": None,
    "close_time": "2024-11-05T23:00:00Z",
    "expiration_time": "2024-11-06T12:00:00Z",
    "status": "finalized",
    "result": "no",
}

SAMPLE_FILL = {
    "trade_id": "trade-abc-123",
    "ticker": "PRES-2024-DEM",
    "side": "yes",
    "action": "buy",
    "count": 10,
    "yes_price": 62,
    "created_time": "2024-10-01T10:00:00Z",
}

SAMPLE_SETTLEMENT = {
    "ticker": "PRES-2024-DEM",
    "market_result": "no",
    "revenue": -620,  # lost 10 contracts × 62 cents
    "updated_time": "2024-11-06T14:00:00Z",
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


def test_normalise_market_unresolved():
    raw = {**SAMPLE_MARKET, "status": "open", "result": None}
    m = normalise_market(raw)
    assert m["resolved"] is False
    assert m["outcome"] is None


# ---------------------------------------------------------------------------
# normalise_fill
# ---------------------------------------------------------------------------

def test_normalise_fill_probability():
    f = normalise_fill(SAMPLE_FILL, user_id="user-1")
    assert f["predicted_probability"] == pytest.approx(0.62)


def test_normalise_fill_fields():
    f = normalise_fill(SAMPLE_FILL, user_id="user-1")
    assert f["source"] == "kalshi"
    assert f["external_id"] == "trade-abc-123"
    assert f["market_external_id"] == "PRES-2024-DEM"
    assert f["user_external_id"] == "user-1"
    assert f["side"] == "yes"
    assert f["action"] == "buy"
    assert f["count"] == 10
    assert f["yes_price"] == 62
    assert f["currency"] == "USD"


def test_normalise_fill_missing_price():
    fill = {**SAMPLE_FILL, "yes_price": None}
    f = normalise_fill(fill, user_id="user-1")
    assert f["predicted_probability"] is None


def test_normalise_fill_timestamp():
    f = normalise_fill(SAMPLE_FILL, user_id="user-1")
    assert f["placed_at"] is not None


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


def test_normalise_settlement_timestamp():
    s = normalise_settlement(SAMPLE_SETTLEMENT, user_id="user-1")
    assert s["settled_at"] is not None


def test_normalise_settlement_missing_time():
    raw = {**SAMPLE_SETTLEMENT, "updated_time": None}
    s = normalise_settlement(raw, user_id="user-1")
    assert s["settled_at"] is None
