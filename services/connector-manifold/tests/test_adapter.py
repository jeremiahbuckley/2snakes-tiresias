"""Unit tests for the Manifold adapter (no network calls)."""

import pytest
from connector_manifold.adapter import normalise_market, normalise_prediction

SAMPLE_MARKET = {
    "id": "manifold-mkt-789",
    "question": "Will OpenAI release GPT-5 in 2024?",
    "description": "Resolves YES if OpenAI officially announces GPT-5 before Jan 1 2025.",
    "resolutionCriteria": "Official OpenAI announcement.",
    "closeTime": 1735689600000,   # 2025-01-01 UTC in ms
    "resolutionTime": 1735700000000,
    "isResolved": True,
    "resolution": "YES",
    "mechanism": "cpmm-1",
}

SAMPLE_BET = {
    "id": "bet-mfld-001",
    "contractId": "manifold-mkt-789",
    "probAfter": 0.83,
    "createdTime": 1720000000000,
}


def test_normalise_market():
    m = normalise_market(SAMPLE_MARKET)
    assert m["external_id"] == "manifold-mkt-789"
    assert m["source"] == "manifold"
    assert m["resolved"] is True
    assert m["outcome"] == "YES"


def test_normalise_prediction():
    p = normalise_prediction(SAMPLE_BET, user_id="user-3")
    assert p["predicted_probability"] == pytest.approx(0.83)
    assert p["market_external_id"] == "manifold-mkt-789"
