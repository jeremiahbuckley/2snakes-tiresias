"""Unit tests for the Metaculus adapter (no network calls).

Fixtures model the v2.0 OAS3 API response format:
- Top-level entity is a Post with an embedded Question.
- Resolution is a string ("yes"/"no"/"annulled"/"ambiguous") or None.
- Timestamps are ISO-8601 strings.
- Tags come from post["projects"]["category"][*]["slug"].
- User's forecast history is in question["my_forecasts"] (oldest-first list).
"""

import pytest
from connector_metaculus.adapter import normalise_forecast, normalise_market

# ---------------------------------------------------------------------------
# Sample fixtures
# ---------------------------------------------------------------------------

SAMPLE_POST_RESOLVED_YES = {
    "id": 12345,
    "title": "Will there be a nuclear weapon detonated in conflict before 2030?",
    "short_title": "Nuclear weapon in conflict before 2030?",
    "slug": "nuclear-weapon-conflict-2030",
    "status": "resolved",
    "resolved": True,
    "nr_forecasters": 412,
    "forecasts_count": 1085,
    "projects": {
        "category": [
            {"id": 10, "name": "Geopolitics", "slug": "geopolitics", "emoji": "🌍", "description": "Geopolitics", "type": "category"},
            {"id": 11, "name": "Nuclear", "slug": "nuclear", "emoji": "☢️", "description": "Nuclear Technology & Risks", "type": "category"},
        ]
    },
    "question": {
        "id": 9876,
        "title": "Will there be a nuclear weapon detonated in conflict before 2030?",
        "description": "This question resolves YES if a nuclear weapon is detonated in armed conflict.",
        "resolution_criteria": "Any credible report of a nuclear detonation in armed conflict.",
        "fine_print": "Excludes test detonations.",
        "type": "binary",
        "status": "resolved",
        "resolution": "no",
        "actual_close_time": "2029-12-31T23:59:59Z",
        "scheduled_close_time": "2029-12-31T23:59:59Z",
        "actual_resolve_time": "2030-01-05T12:00:00Z",
        "scheduled_resolve_time": "2030-01-15T00:00:00Z",
        "my_forecasts": [
            {
                "probability_yes": 0.03,
                "start_time": "2024-06-01T10:00:00Z",
                "end_time": "2025-01-10T12:00:00Z",
            },
            {
                "probability_yes": 0.04,
                "start_time": "2025-01-10T12:00:00Z",
                "end_time": None,
            },
        ],
    },
}

SAMPLE_POST_OPEN = {
    "id": 55555,
    "title": "Will AGI be achieved before 2030?",
    "short_title": "AGI before 2030?",
    "slug": "agi-before-2030",
    "status": "open",
    "resolved": False,
    "nr_forecasters": 890,
    "forecasts_count": 3200,
    "projects": {
        "category": [
            {"id": 20, "name": "Artificial Intelligence", "slug": "artificial-intelligence", "emoji": "🤖", "description": "Artificial Intelligence", "type": "category"},
        ]
    },
    "question": {
        "id": 44444,
        "title": "Will AGI be achieved before 2030?",
        "description": "Resolves YES if a system passes a comprehensive AGI benchmark.",
        "resolution_criteria": "ARC-AGI score above 95% or equivalent.",
        "fine_print": "",
        "type": "binary",
        "status": "open",
        "resolution": None,
        "actual_close_time": None,
        "scheduled_close_time": "2029-12-31T23:59:59Z",
        "actual_resolve_time": None,
        "scheduled_resolve_time": "2030-06-01T00:00:00Z",
        "my_forecasts": [
            {
                "probability_yes": 0.22,
                "start_time": "2025-03-15T08:00:00Z",
                "end_time": None,
            }
        ],
    },
}

SAMPLE_POST_NO_FORECASTS = {
    "id": 77777,
    "title": "Will X happen?",
    "status": "open",
    "resolved": False,
    "projects": {},
    "question": {
        "id": 66666,
        "type": "binary",
        "status": "open",
        "resolution": None,
        "actual_close_time": None,
        "scheduled_close_time": "2026-01-01T00:00:00Z",
        "actual_resolve_time": None,
        "scheduled_resolve_time": "2026-06-01T00:00:00Z",
        "my_forecasts": [],   # edge case: user somehow in forecaster list but no forecast recorded
    },
}

# The Metaculus v2 detail endpoint returns my_forecasts as:
#   { "history": [...], "latest": {...}, "score_data": {} }
# Each entry has forecast_values = [P(NO), P(YES)] and Unix float timestamps,
# NOT the probability_yes / ISO-8601 fields the list endpoint used to return.
#
# 1735689600.0 = 2025-01-01T00:00:00Z
# 1748736000.0 = 2025-06-01T00:00:00Z
SAMPLE_POST_MY_FORECASTS_AS_DICT = {
    "id": 43265,
    "title": "Will the economy enter a recession in 2026?",
    "status": "open",
    "resolved": False,
    "projects": {},
    "question": {
        "id": 43265,
        "type": "binary",
        "status": "open",
        "resolution": None,
        "actual_close_time": None,
        "scheduled_close_time": "2026-12-31T23:59:59Z",
        "actual_resolve_time": None,
        "scheduled_resolve_time": "2027-03-01T00:00:00Z",
        "my_forecasts": {
            "history": [
                {
                    "question_id": 43265,
                    "author_id": 300060,
                    "start_time": 1735689600.0,   # 2025-01-01T00:00:00Z
                    "end_time": 1748736000.0,
                    "forecast_values": [0.45, 0.55],  # [P(NO), P(YES)]
                },
                {
                    "question_id": 43265,
                    "author_id": 300060,
                    "start_time": 1748736000.0,   # 2025-06-01T00:00:00Z
                    "end_time": 1777777600.0,
                    "forecast_values": [0.37, 0.63],
                },
            ],
            "latest": {
                "question_id": 43265,
                "author_id": 300060,
                "start_time": 1748736000.0,       # 2025-06-01T00:00:00Z
                "end_time": 1777777600.0,
                "forecast_values": [0.37, 0.63],
            },
            "score_data": {},
        },
    },
}

SAMPLE_POST_MY_FORECASTS_AS_EMPTY_DICT = {
    "id": 43266,
    "title": "Another question",
    "status": "open",
    "resolved": False,
    "projects": {},
    "question": {
        "id": 43266,
        "type": "binary",
        "status": "open",
        "resolution": None,
        "actual_close_time": None,
        "scheduled_close_time": "2026-12-31T23:59:59Z",
        "actual_resolve_time": None,
        "scheduled_resolve_time": "2027-03-01T00:00:00Z",
        "my_forecasts": {
            "history": [],
            "latest": None,
            "score_data": {},
        },
    },
}


# ---------------------------------------------------------------------------
# normalise_market
# ---------------------------------------------------------------------------

def test_normalise_market_external_id():
    m = normalise_market(SAMPLE_POST_RESOLVED_YES)
    assert m["external_id"] == "12345"


def test_normalise_market_source():
    m = normalise_market(SAMPLE_POST_RESOLVED_YES)
    assert m["source"] == "metaculus"


def test_normalise_market_title():
    m = normalise_market(SAMPLE_POST_RESOLVED_YES)
    assert "nuclear" in m["title"].lower()


def test_normalise_market_description_and_criteria():
    m = normalise_market(SAMPLE_POST_RESOLVED_YES)
    assert "nuclear" in m["description"].lower()
    assert m["resolution_criteria"] is not None
    assert m["fine_print"] == "Excludes test detonations."


def test_normalise_market_resolved_yes():
    m = normalise_market(SAMPLE_POST_RESOLVED_YES)
    assert m["resolved"] is True
    assert m["outcome"] == "no"          # question resolved NO


def test_normalise_market_unresolved():
    m = normalise_market(SAMPLE_POST_OPEN)
    assert m["resolved"] is False
    assert m["outcome"] is None


def test_normalise_market_timestamps_resolved():
    m = normalise_market(SAMPLE_POST_RESOLVED_YES)
    assert m["closes_at"] is not None
    assert m["resolves_at"] is not None
    # actual_resolve_time should be preferred over scheduled
    assert m["resolves_at"].year == 2030
    assert m["resolves_at"].month == 1
    assert m["resolves_at"].day == 5


def test_normalise_market_timestamps_open_falls_back_to_scheduled():
    m = normalise_market(SAMPLE_POST_OPEN)
    # No actual_close_time → falls back to scheduled_close_time
    assert m["closes_at"] is not None
    assert m["closes_at"].year == 2029


def test_normalise_market_tags():
    m = normalise_market(SAMPLE_POST_RESOLVED_YES)
    assert "geopolitics" in m["tags"]
    assert "nuclear" in m["tags"]


def test_normalise_market_empty_tags():
    m = normalise_market(SAMPLE_POST_NO_FORECASTS)
    assert m["tags"] == []


def test_normalise_market_question_type():
    m = normalise_market(SAMPLE_POST_RESOLVED_YES)
    assert m["question_type"] == "binary"


# ---------------------------------------------------------------------------
# normalise_forecast
# ---------------------------------------------------------------------------

def test_normalise_forecast_fields():
    f = normalise_forecast(SAMPLE_POST_RESOLVED_YES, user_id="user-4")
    assert f["source"] == "metaculus"
    assert f["user_external_id"] == "user-4"
    assert f["market_external_id"] == "12345"


def test_normalise_forecast_external_id():
    f = normalise_forecast(SAMPLE_POST_RESOLVED_YES, user_id="user-4")
    # Compound ID since REST API doesn't return a unique forecast record ID
    assert "metaculus" in f["external_id"]
    assert "12345" in f["external_id"]
    assert "user-4" in f["external_id"]


def test_normalise_forecast_probability_latest():
    """Should use the LAST entry in my_forecasts (most recent update)."""
    f = normalise_forecast(SAMPLE_POST_RESOLVED_YES, user_id="user-4")
    assert f["predicted_probability"] == pytest.approx(0.04)


def test_normalise_forecast_single_entry():
    f = normalise_forecast(SAMPLE_POST_OPEN, user_id="user-4")
    assert f["predicted_probability"] == pytest.approx(0.22)


def test_normalise_forecast_placed_at():
    f = normalise_forecast(SAMPLE_POST_RESOLVED_YES, user_id="user-4")
    # start_time of the last forecast entry
    assert f["placed_at"] is not None
    assert f["placed_at"].year == 2025


def test_normalise_forecast_no_forecasts_returns_none_probability():
    """Edge case: my_forecasts is empty → probability is None (not an error)."""
    f = normalise_forecast(SAMPLE_POST_NO_FORECASTS, user_id="user-4")
    assert f["predicted_probability"] is None
    assert f["placed_at"] is None


# ---------------------------------------------------------------------------
# normalise_forecast — my_forecasts dict (Metaculus detail endpoint format)
# ---------------------------------------------------------------------------

def test_normalise_forecast_my_forecasts_as_dict_probability():
    """Detail endpoint: probability comes from latest.forecast_values[1] (P(YES))."""
    f = normalise_forecast(SAMPLE_POST_MY_FORECASTS_AS_DICT, user_id="user-7")
    assert f["predicted_probability"] == pytest.approx(0.63)


def test_normalise_forecast_my_forecasts_as_dict_placed_at():
    """placed_at comes from latest.start_time which is a Unix float, not ISO-8601."""
    f = normalise_forecast(SAMPLE_POST_MY_FORECASTS_AS_DICT, user_id="user-7")
    assert f["placed_at"] is not None
    assert f["placed_at"].year == 2025
    assert f["placed_at"].month == 6


def test_normalise_forecast_my_forecasts_as_dict_fields():
    """Other fields are unaffected when my_forecasts is a dict."""
    f = normalise_forecast(SAMPLE_POST_MY_FORECASTS_AS_DICT, user_id="user-7")
    assert f["source"] == "metaculus"
    assert f["market_external_id"] == "43265"
    assert "user-7" in f["external_id"]


def test_normalise_forecast_my_forecasts_empty_dict_returns_none():
    """Empty results list inside dict → probability is None (not an error)."""
    f = normalise_forecast(SAMPLE_POST_MY_FORECASTS_AS_EMPTY_DICT, user_id="user-7")
    assert f["predicted_probability"] is None
    assert f["placed_at"] is None
