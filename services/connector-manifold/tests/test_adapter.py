"""Unit tests for the Manifold adapter (no network calls)."""

import pytest
from connector_manifold.adapter import normalise_bet, normalise_market

# ---------------------------------------------------------------------------
# Sample fixtures
# ---------------------------------------------------------------------------

SAMPLE_MARKET = {
    "id": "manifold-mkt-789",
    "question": "Will OpenAI release GPT-5 in 2024?",
    # description is a TipTap JSONContent blob — should NOT be used
    "description": {"type": "doc", "content": [{"type": "paragraph"}]},
    "textDescription": "Resolves YES if OpenAI officially announces GPT-5 before Jan 1 2025.",
    "resolutionCriteria": "Official OpenAI announcement.",
    "closeTime": 1735689600000,     # 2025-01-01 UTC in ms
    "resolutionTime": 1735700000000,
    "isResolved": True,
    "resolution": "YES",
    "mechanism": "cpmm-1",
    "groupSlugs": ["ai", "technology"],
}

SAMPLE_MARKET_OPEN = {
    "id": "manifold-mkt-open-1",
    "question": "Will ETH surpass $10k in 2025?",
    "textDescription": "Resolves YES if ETH/USD closes above $10,000.",
    "resolutionCriteria": "CoinGecko daily close.",
    "closeTime": 1767225600000,     # 2026-01-01 UTC in ms
    "isResolved": False,
    "resolution": None,
    "mechanism": "cpmm-1",
    "groupSlugs": [],
}

# Standard YES bet
SAMPLE_BET_YES = {
    "id": "bet-mfld-001",
    "contractId": "manifold-mkt-789",
    "outcome": "YES",
    "amount": 50.0,
    "shares": 65.3,
    "probBefore": 0.60,
    "probAfter": 0.65,
    "createdTime": 1720000000000,
    "isRedemption": False,
}

# NO bet — implied YES probability should be inverted
SAMPLE_BET_NO = {
    "id": "bet-mfld-002",
    "contractId": "manifold-mkt-789",
    "outcome": "NO",
    "amount": 30.0,
    "shares": 45.0,
    "probBefore": 0.65,
    "probAfter": 0.58,
    "createdTime": 1720100000000,
    "isRedemption": False,
}

# Redemption bet — should be filtered out by sync, not scored
SAMPLE_BET_REDEMPTION = {
    "id": "bet-mfld-003",
    "contractId": "manifold-mkt-789",
    "outcome": "YES",
    "amount": -10.0,
    "shares": -10.0,
    "probBefore": 0.65,
    "probAfter": 0.65,
    "createdTime": 1735700001000,
    "isRedemption": True,
}


# ---------------------------------------------------------------------------
# normalise_market
# ---------------------------------------------------------------------------

def test_normalise_market_external_id():
    m = normalise_market(SAMPLE_MARKET)
    assert m["external_id"] == "manifold-mkt-789"


def test_normalise_market_basic_fields():
    m = normalise_market(SAMPLE_MARKET)
    assert m["source"] == "manifold"
    assert m["title"] == "Will OpenAI release GPT-5 in 2024?"
    assert m["resolution_criteria"] == "Official OpenAI announcement."


def test_normalise_market_uses_text_description():
    """description should be the plain-text field, not the TipTap JSON blob."""
    m = normalise_market(SAMPLE_MARKET)
    assert isinstance(m["description"], str)
    assert "GPT-5" in m["description"]


def test_normalise_market_resolved():
    m = normalise_market(SAMPLE_MARKET)
    assert m["resolved"] is True
    assert m["outcome"] == "YES"


def test_normalise_market_unresolved():
    m = normalise_market(SAMPLE_MARKET_OPEN)
    assert m["resolved"] is False
    assert m["outcome"] is None


def test_normalise_market_timestamp():
    m = normalise_market(SAMPLE_MARKET)
    assert m["closes_at"] is not None
    assert m["resolves_at"] is not None


def test_normalise_market_tags():
    m = normalise_market(SAMPLE_MARKET)
    assert "ai" in m["tags"]
    assert "technology" in m["tags"]


def test_normalise_market_empty_tags():
    m = normalise_market(SAMPLE_MARKET_OPEN)
    assert m["tags"] == []


# ---------------------------------------------------------------------------
# normalise_bet
# ---------------------------------------------------------------------------

def test_normalise_bet_fields():
    b = normalise_bet(SAMPLE_BET_YES, user_id="user-3")
    assert b["external_id"] == "bet-mfld-001"
    assert b["source"] == "manifold"
    assert b["user_external_id"] == "user-3"
    assert b["market_external_id"] == "manifold-mkt-789"
    assert b["outcome"] == "YES"
    assert b["amount"] == pytest.approx(50.0)
    assert b["currency"] == "MANA"


def test_normalise_bet_yes_probability():
    """YES bet at probBefore=0.60 → predicted_probability 0.60."""
    b = normalise_bet(SAMPLE_BET_YES, user_id="user-3")
    assert b["predicted_probability"] == pytest.approx(0.60)


def test_normalise_bet_no_probability():
    """NO bet at probBefore=0.65 → implied YES probability = 1 - 0.65 = 0.35."""
    b = normalise_bet(SAMPLE_BET_NO, user_id="user-3")
    assert b["predicted_probability"] == pytest.approx(0.35)


def test_normalise_bet_prob_before_and_after():
    b = normalise_bet(SAMPLE_BET_YES, user_id="user-3")
    assert b["prob_before"] == pytest.approx(0.60)
    assert b["prob_after"] == pytest.approx(0.65)


def test_normalise_bet_timestamp():
    b = normalise_bet(SAMPLE_BET_YES, user_id="user-3")
    assert b["placed_at"] is not None


def test_normalise_bet_is_redemption_false():
    b = normalise_bet(SAMPLE_BET_YES, user_id="user-3")
    assert b["is_redemption"] is False


def test_normalise_bet_is_redemption_true():
    b = normalise_bet(SAMPLE_BET_REDEMPTION, user_id="user-3")
    assert b["is_redemption"] is True
