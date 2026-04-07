"""Unit tests for the Polymarket adapter (no network calls)."""

import pytest
from connector_polymarket.adapter import normalise_market, normalise_prediction

SAMPLE_MARKET = {
    "condition_id": "0xabc123",
    "question": "Will Bitcoin exceed $100k by end of 2024?",
    "description": "Resolves YES if BTC/USD closes above $100,000 on any major exchange.",
    "resolution_source": "CoinGecko",
    "end_date_iso": "2024-12-31T23:59:59Z",
    "closed": True,
    "winning_side": "yes",
}

SAMPLE_TRADE = {
    "id": "trade-poly-456",
    "market": "0xabc123",
    "price": 0.75,
    "created_at": "2024-06-15T09:30:00Z",
}


def test_normalise_market():
    m = normalise_market(SAMPLE_MARKET)
    assert m["external_id"] == "0xabc123"
    assert m["source"] == "polymarket"
    assert m["resolved"] is True
    assert m["outcome"] == "yes"


def test_normalise_prediction():
    p = normalise_prediction(SAMPLE_TRADE, user_id="user-2")
    assert p["predicted_probability"] == pytest.approx(0.75)
    assert p["source"] == "polymarket"
