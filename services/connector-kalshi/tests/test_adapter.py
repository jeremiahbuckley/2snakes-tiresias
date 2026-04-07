"""
Unit tests for the Kalshi adapter.

These tests use only static fixture data — no network calls.
"""

import pytest
from connector_kalshi.adapter import normalise_market, normalise_prediction


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

SAMPLE_TRADE = {
    "trade_id": "trade-abc-123",
    "ticker": "PRES-2024-DEM",
    "yes_price": 62,
    "created_time": "2024-10-01T10:00:00Z",
}


def test_normalise_market_fields():
    m = normalise_market(SAMPLE_MARKET)
    assert m["external_id"] == "PRES-2024-DEM"
    assert m["source"] == "kalshi"
    assert m["resolved"] is True
    assert m["outcome"] == "no"


def test_normalise_market_timestamps():
    m = normalise_market(SAMPLE_MARKET)
    assert m["closes_at"] is not None
    assert m["resolves_at"] is not None


def test_normalise_prediction_probability():
    p = normalise_prediction(SAMPLE_TRADE, user_id="user-1")
    assert p["predicted_probability"] == pytest.approx(0.62)
    assert p["source"] == "kalshi"
    assert p["market_external_id"] == "PRES-2024-DEM"


def test_normalise_prediction_missing_price():
    trade = {**SAMPLE_TRADE, "yes_price": None}
    p = normalise_prediction(trade, user_id="user-1")
    assert p["predicted_probability"] is None
