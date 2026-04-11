"""Unit tests for the Polymarket adapter (no network calls)."""

import json
import pytest
from connector_polymarket.adapter import (
    normalise_closed_position,
    normalise_market,
    normalise_trade,
)

# Gamma API market — note conditionId (not condition_id), JSON-string outcomes,
# and tags embedded via include_tag=true
SAMPLE_MARKET = {
    "conditionId": "0xdd22472e552920b8438158ea7238bfadfa4f736aa4cee91a6b86c39ead110917",
    "question": "Will Bitcoin exceed $100k by end of 2024?",
    "description": "Resolves YES if BTC/USD closes above $100,000 on any major exchange.",
    "resolutionSource": "CoinGecko",
    "endDateIso": "2024-12-31T23:59:59Z",
    "closed": True,
    "outcomes": json.dumps(["Yes", "No"]),
    "outcomePrices": json.dumps(["1", "0"]),  # Yes won
    "tags": [{"id": "1", "label": "Crypto", "slug": "crypto"}],
}

SAMPLE_MARKET_UNRESOLVED = {
    "conditionId": "0xabc123abc123abc123abc123abc123abc123abc123abc123abc123abc123abc1",
    "question": "Will ETH flip BTC by 2025?",
    "description": "Resolves YES if ETH market cap exceeds BTC.",
    "resolutionSource": "CoinGecko",
    "endDateIso": "2025-12-31T23:59:59Z",
    "closed": False,
    "outcomes": json.dumps(["Yes", "No"]),
    "outcomePrices": json.dumps(["0.35", "0.65"]),  # unresolved — no price at 1.0
    "tags": [],
}

# Data API trade — conditionId, transactionHash, Unix timestamp
SAMPLE_TRADE = {
    "transactionHash": "0xdeadbeef",
    "conditionId": "0xdd22472e552920b8438158ea7238bfadfa4f736aa4cee91a6b86c39ead110917",
    "side": "BUY",
    "outcome": "Yes",
    "outcomeIndex": 0,
    "price": 0.75,
    "size": 100.0,
    "timestamp": 1718444400,  # Unix seconds
    "slug": "will-bitcoin-exceed-100k-by-end-of-2024",
}

SAMPLE_TRADE_NO_OUTCOME = {
    "transactionHash": "BUY of No token",
    "conditionId": "0xdd22472e552920b8438158ea7238bfadfa4f736aa4cee91a6b86c39ead110917",
    "side": "BUY",
    "outcome": "No",
    "outcomeIndex": 1,
    "price": 0.30,
    "size": 50.0,
    "timestamp": 1718444400,
    "slug": "will-bitcoin-exceed-100k-by-end-of-2024",
}

# Data API closed position
SAMPLE_CLOSED_POSITION = {
    "proxyWallet": "0x56687bf447db6ffa42ffe2204a05edaa20f55839",
    "conditionId": "0xdd22472e552920b8438158ea7238bfadfa4f736aa4cee91a6b86c39ead110917",
    "outcome": "Yes",
    "outcomeIndex": 0,
    "avgPrice": 0.72,
    "totalBought": 720.0,
    "realizedPnl": 280.0,
    "endDate": "2025-01-02T00:00:00Z",
    "title": "Will Bitcoin exceed $100k by end of 2024?",
    "slug": "will-bitcoin-exceed-100k-by-end-of-2024",
}


# ---------------------------------------------------------------------------
# normalise_market
# ---------------------------------------------------------------------------

def test_normalise_market_external_id():
    m = normalise_market(SAMPLE_MARKET)
    assert m["external_id"] == "0xdd22472e552920b8438158ea7238bfadfa4f736aa4cee91a6b86c39ead110917"


def test_normalise_market_basic_fields():
    m = normalise_market(SAMPLE_MARKET)
    assert m["source"] == "polymarket"
    assert m["title"] == "Will Bitcoin exceed $100k by end of 2024?"
    assert m["resolution_criteria"] == "CoinGecko"
    assert m["resolved"] is True


def test_normalise_market_winning_outcome():
    m = normalise_market(SAMPLE_MARKET)
    assert m["outcome"] == "Yes"


def test_normalise_market_unresolved_outcome():
    m = normalise_market(SAMPLE_MARKET_UNRESOLVED)
    assert m["resolved"] is False
    assert m["outcome"] is None


def test_normalise_market_timestamp():
    m = normalise_market(SAMPLE_MARKET)
    assert m["closes_at"] is not None


def test_normalise_market_tags():
    m = normalise_market(SAMPLE_MARKET)
    assert "crypto" in m["tags"]


def test_normalise_market_empty_tags():
    m = normalise_market(SAMPLE_MARKET_UNRESOLVED)
    assert m["tags"] == []


# ---------------------------------------------------------------------------
# normalise_trade
# ---------------------------------------------------------------------------

def test_normalise_trade_fields():
    t = normalise_trade(SAMPLE_TRADE, user_id="user-2")
    assert t["external_id"] == "0xdeadbeef"
    assert t["source"] == "polymarket"
    assert t["user_external_id"] == "user-2"
    assert t["market_external_id"] == "0xdd22472e552920b8438158ea7238bfadfa4f736aa4cee91a6b86c39ead110917"
    assert t["side"] == "BUY"
    assert t["outcome"] == "Yes"
    assert t["size"] == 100.0
    assert t["price"] == 0.75


def test_normalise_trade_yes_probability():
    """BUY of Yes token at 0.75 → probability 0.75."""
    t = normalise_trade(SAMPLE_TRADE, user_id="user-2")
    assert t["predicted_probability"] == pytest.approx(0.75)


def test_normalise_trade_no_token_probability():
    """BUY of No token at 0.30 → implied Yes probability = 1 - 0.30 = 0.70."""
    t = normalise_trade(SAMPLE_TRADE_NO_OUTCOME, user_id="user-2")
    assert t["predicted_probability"] == pytest.approx(0.70)


def test_normalise_trade_timestamp():
    t = normalise_trade(SAMPLE_TRADE, user_id="user-2")
    assert t["placed_at"] is not None


def test_normalise_trade_slug_retained():
    t = normalise_trade(SAMPLE_TRADE, user_id="user-2")
    assert t["slug"] == "will-bitcoin-exceed-100k-by-end-of-2024"


# ---------------------------------------------------------------------------
# normalise_closed_position
# ---------------------------------------------------------------------------

def test_normalise_closed_position_fields():
    p = normalise_closed_position(SAMPLE_CLOSED_POSITION, user_id="user-2")
    assert p["source"] == "polymarket"
    assert p["user_external_id"] == "user-2"
    assert p["market_external_id"] == "0xdd22472e552920b8438158ea7238bfadfa4f736aa4cee91a6b86c39ead110917"
    assert p["outcome"] == "Yes"
    assert p["avg_price"] == pytest.approx(0.72)
    assert p["realized_pnl"] == pytest.approx(280.0)


def test_normalise_closed_position_timestamp():
    p = normalise_closed_position(SAMPLE_CLOSED_POSITION, user_id="user-2")
    assert p["closed_at"] is not None


def test_normalise_closed_position_slug_retained():
    p = normalise_closed_position(SAMPLE_CLOSED_POSITION, user_id="user-2")
    assert p["slug"] == "will-bitcoin-exceed-100k-by-end-of-2024"
