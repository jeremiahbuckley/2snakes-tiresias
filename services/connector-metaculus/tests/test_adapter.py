"""Unit tests for the Metaculus adapter (no network calls)."""

import pytest
from connector_metaculus.adapter import normalise_market, normalise_prediction

SAMPLE_QUESTION = {
    "id": 12345,
    "title": "Will there be a nuclear weapon detonated in conflict before 2030?",
    "description": "This question resolves YES if...",
    "resolution_criteria": "Any credible report of a nuclear detonation in armed conflict.",
    "close_time": "2029-12-31T23:59:59Z",
    "resolve_time": "2030-01-15T00:00:00Z",
    "resolution": 0,  # resolved NO
}

SAMPLE_PREDICTION = {
    "id": 98765,
    "question": 12345,
    "prediction": 0.04,
    "t": "2025-01-10T12:00:00Z",
}


def test_normalise_market_resolved_no():
    m = normalise_market(SAMPLE_QUESTION)
    assert m["external_id"] == "12345"
    assert m["source"] == "metaculus"
    assert m["resolved"] is True
    assert m["outcome"] == "no"


def test_normalise_market_unresolved():
    q = {**SAMPLE_QUESTION, "resolution": None}
    m = normalise_market(q)
    assert m["resolved"] is False
    assert m["outcome"] is None


def test_normalise_prediction():
    p = normalise_prediction(SAMPLE_PREDICTION, user_id="user-4")
    assert p["predicted_probability"] == pytest.approx(0.04)
    assert p["market_external_id"] == "12345"
