"""
Tests for connector_metaculus/sync.py.

All tests mock MetaculusClient so no network calls are made.

Patching strategy
-----------------
- For sync_user_forecasts / sync_market: patch the MetaculusClient CLASS in
  connector_metaculus.sync (i.e. "connector_metaculus.sync.MetaculusClient")
  so the constructor never runs. The class mock's return_value is the instance.
- For the client-level pagination test: patch
  "connector_metaculus.client.httpx.AsyncClient" so we never touch the real
  httpx transport (which tries to open a SOCKS proxy in the sandbox).

Coverage
--------
  sync_user_forecasts — binary-only filter, empty results, no-forecast edge case,
                        probability value, source field, compound external_id
  sync_market         — normalised dict shape, resolved/open, tags, timestamps
  pagination          — get_user_posts follows `next` links until exhausted
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest


# ---------------------------------------------------------------------------
# Shared fixtures (same response shape as test_adapter.py)
# ---------------------------------------------------------------------------

BINARY_POST_RESOLVED = {
    "id": 10001,
    "title": "Will a large earthquake hit California before 2027?",
    "resolved": True,
    "categories": [{"id": 5, "name": "Geophysics", "slug": "geophysics", "description": ""}],
    "question": {
        "id": 8001,
        "type": "binary",
        "status": "resolved",
        "resolution": "yes",
        "actual_close_time": "2026-12-31T23:59:59Z",
        "scheduled_close_time": "2026-12-31T23:59:59Z",
        "actual_resolve_time": "2027-01-03T10:00:00Z",
        "scheduled_resolve_time": "2027-01-15T00:00:00Z",
        "my_forecasts": [
            {"probability_yes": 0.55, "start_time": "2025-01-01T00:00:00Z", "end_time": "2025-06-01T00:00:00Z"},
            {"probability_yes": 0.60, "start_time": "2025-06-01T00:00:00Z", "end_time": None},
        ],
    },
}

BINARY_POST_OPEN = {
    "id": 10002,
    "title": "Will fusion power be commercially viable before 2035?",
    "resolved": False,
    "categories": [{"id": 6, "name": "Energy", "slug": "energy", "description": ""}],
    "question": {
        "id": 8002,
        "type": "binary",
        "status": "open",
        "resolution": None,
        "actual_close_time": None,
        "scheduled_close_time": "2034-12-31T23:59:59Z",
        "actual_resolve_time": None,
        "scheduled_resolve_time": "2035-06-01T00:00:00Z",
        "my_forecasts": [
            {"probability_yes": 0.12, "start_time": "2025-03-01T08:00:00Z", "end_time": None},
        ],
    },
}

NUMERIC_POST = {
    "id": 10003,
    "title": "What will the global average temperature anomaly be in 2030?",
    "resolved": False,
    "categories": [],
    "question": {
        "id": 8003,
        "type": "numeric",   # NOT binary — should be filtered out in v1
        "status": "open",
        "resolution": None,
        "actual_close_time": None,
        "scheduled_close_time": "2030-12-31T23:59:59Z",
        "my_forecasts": [],
    },
}

MULTIPLE_CHOICE_POST = {
    "id": 10004,
    "title": "Which party will win the next UK general election?",
    "resolved": False,
    "categories": [],
    "question": {
        "id": 8004,
        "type": "multiple_choice",   # NOT binary
        "status": "open",
        "resolution": None,
        "my_forecasts": [],
    },
}

POST_NO_FORECASTS = {
    "id": 10005,
    "title": "Will event X occur?",
    "resolved": False,
    "categories": [],
    "question": {
        "id": 8005,
        "type": "binary",
        "status": "open",
        "resolution": None,
        "actual_close_time": None,
        "scheduled_close_time": "2027-01-01T00:00:00Z",
        "my_forecasts": [],   # empty — edge case
    },
}

POST_NO_QUESTION = {
    # A post with group_of_questions or conditional has no top-level "question"
    "id": 10006,
    "title": "A group post",
    "resolved": False,
    "categories": [],
    "question": None,
}


def _make_client_mock(get_user_posts_return=None, get_post_return=None):
    """Return a mock MetaculusClient class whose instances behave as configured."""
    instance = MagicMock()
    instance.get_user_posts = AsyncMock(return_value=get_user_posts_return or [])
    instance.get_post = AsyncMock(return_value=get_post_return or {})

    cls_mock = MagicMock(return_value=instance)
    return cls_mock, instance


# ---------------------------------------------------------------------------
# sync_user_forecasts
# ---------------------------------------------------------------------------

class TestSyncUserForecasts:

    @pytest.mark.asyncio
    async def test_returns_only_binary_forecasts(self):
        """Non-binary questions (numeric, multiple_choice, None) are skipped."""
        posts = [
            BINARY_POST_RESOLVED,
            BINARY_POST_OPEN,
            NUMERIC_POST,
            MULTIPLE_CHOICE_POST,
            POST_NO_QUESTION,
        ]
        cls_mock, instance = _make_client_mock(get_user_posts_return=posts)

        with patch("connector_metaculus.sync.MetaculusClient", cls_mock):
            from connector_metaculus.sync import sync_user_forecasts
            results = await sync_user_forecasts(user_id="user-99", metaculus_user_id=12345)

        # Only the two binary posts should appear
        assert len(results) == 2
        external_ids = {r["market_external_id"] for r in results}
        assert "10001" in external_ids
        assert "10002" in external_ids

    @pytest.mark.asyncio
    async def test_forecast_uses_last_my_forecasts_entry(self):
        """The most recent forecast (last entry in my_forecasts) is used."""
        cls_mock, _ = _make_client_mock(get_user_posts_return=[BINARY_POST_RESOLVED])

        with patch("connector_metaculus.sync.MetaculusClient", cls_mock):
            from connector_metaculus.sync import sync_user_forecasts
            results = await sync_user_forecasts(user_id="user-1", metaculus_user_id=9)

        assert len(results) == 1
        # BINARY_POST_RESOLVED has two entries; last is 0.60
        assert results[0]["predicted_probability"] == pytest.approx(0.60)

    @pytest.mark.asyncio
    async def test_empty_api_response_returns_empty_list(self):
        cls_mock, _ = _make_client_mock(get_user_posts_return=[])

        with patch("connector_metaculus.sync.MetaculusClient", cls_mock):
            from connector_metaculus.sync import sync_user_forecasts
            results = await sync_user_forecasts(user_id="user-1", metaculus_user_id=9)

        assert results == []

    @pytest.mark.asyncio
    async def test_post_with_no_forecasts_still_included(self):
        """A binary post with empty my_forecasts is still returned (probability=None)."""
        cls_mock, _ = _make_client_mock(get_user_posts_return=[POST_NO_FORECASTS])

        with patch("connector_metaculus.sync.MetaculusClient", cls_mock):
            from connector_metaculus.sync import sync_user_forecasts
            results = await sync_user_forecasts(user_id="user-1", metaculus_user_id=9)

        assert len(results) == 1
        assert results[0]["predicted_probability"] is None

    @pytest.mark.asyncio
    async def test_source_is_metaculus(self):
        cls_mock, _ = _make_client_mock(get_user_posts_return=[BINARY_POST_OPEN])

        with patch("connector_metaculus.sync.MetaculusClient", cls_mock):
            from connector_metaculus.sync import sync_user_forecasts
            results = await sync_user_forecasts(user_id="user-42", metaculus_user_id=7)

        assert results[0]["source"] == "metaculus"

    @pytest.mark.asyncio
    async def test_external_id_is_compound(self):
        """external_id should embed both post ID and user_id for uniqueness."""
        cls_mock, _ = _make_client_mock(get_user_posts_return=[BINARY_POST_OPEN])

        with patch("connector_metaculus.sync.MetaculusClient", cls_mock):
            from connector_metaculus.sync import sync_user_forecasts
            results = await sync_user_forecasts(user_id="user-42", metaculus_user_id=7)

        ext_id = results[0]["external_id"]
        assert "10002" in ext_id
        assert "user-42" in ext_id

    @pytest.mark.asyncio
    async def test_all_non_binary_posts_returns_empty(self):
        posts = [NUMERIC_POST, MULTIPLE_CHOICE_POST, POST_NO_QUESTION]
        cls_mock, _ = _make_client_mock(get_user_posts_return=posts)

        with patch("connector_metaculus.sync.MetaculusClient", cls_mock):
            from connector_metaculus.sync import sync_user_forecasts
            results = await sync_user_forecasts(user_id="user-1", metaculus_user_id=9)

        assert results == []

    @pytest.mark.asyncio
    async def test_passes_user_id_to_client(self):
        """The metaculus_user_id is forwarded to the API client."""
        cls_mock, instance = _make_client_mock(get_user_posts_return=[])

        with patch("connector_metaculus.sync.MetaculusClient", cls_mock):
            from connector_metaculus.sync import sync_user_forecasts
            await sync_user_forecasts(user_id="user-1", metaculus_user_id=99999)

        instance.get_user_posts.assert_called_once_with(99999)


# ---------------------------------------------------------------------------
# sync_market
# ---------------------------------------------------------------------------

class TestSyncMarket:

    @pytest.mark.asyncio
    async def test_returns_normalised_market(self):
        cls_mock, _ = _make_client_mock(get_post_return=BINARY_POST_RESOLVED)

        with patch("connector_metaculus.sync.MetaculusClient", cls_mock):
            from connector_metaculus.sync import sync_market
            result = await sync_market(post_id=10001)

        assert result["external_id"] == "10001"
        assert result["source"] == "metaculus"
        assert result["resolved"] is True
        assert result["outcome"] == "yes"

    @pytest.mark.asyncio
    async def test_open_market_has_no_outcome(self):
        cls_mock, _ = _make_client_mock(get_post_return=BINARY_POST_OPEN)

        with patch("connector_metaculus.sync.MetaculusClient", cls_mock):
            from connector_metaculus.sync import sync_market
            result = await sync_market(post_id=10002)

        assert result["resolved"] is False
        assert result["outcome"] is None

    @pytest.mark.asyncio
    async def test_tags_extracted_from_categories(self):
        cls_mock, _ = _make_client_mock(get_post_return=BINARY_POST_RESOLVED)

        with patch("connector_metaculus.sync.MetaculusClient", cls_mock):
            from connector_metaculus.sync import sync_market
            result = await sync_market(post_id=10001)

        assert "geophysics" in result["tags"]

    @pytest.mark.asyncio
    async def test_passes_post_id_to_client(self):
        cls_mock, instance = _make_client_mock(get_post_return=BINARY_POST_OPEN)

        with patch("connector_metaculus.sync.MetaculusClient", cls_mock):
            from connector_metaculus.sync import sync_market
            await sync_market(post_id=10002)

        instance.get_post.assert_called_once_with(10002)

    @pytest.mark.asyncio
    async def test_timestamps_are_datetime_objects(self):
        cls_mock, _ = _make_client_mock(get_post_return=BINARY_POST_RESOLVED)

        with patch("connector_metaculus.sync.MetaculusClient", cls_mock):
            from connector_metaculus.sync import sync_market
            result = await sync_market(post_id=10001)

        from datetime import datetime
        assert isinstance(result["closes_at"], datetime)
        assert isinstance(result["resolves_at"], datetime)


# ---------------------------------------------------------------------------
# Pagination — sync_user_forecasts sees all pages
# ---------------------------------------------------------------------------

class TestPagination:

    @pytest.mark.asyncio
    async def test_all_pages_merged_in_sync_user_forecasts(self):
        """sync_user_forecasts receives all posts because the client already paginates."""
        all_posts = [BINARY_POST_RESOLVED, BINARY_POST_OPEN]
        cls_mock, _ = _make_client_mock(get_user_posts_return=all_posts)

        with patch("connector_metaculus.sync.MetaculusClient", cls_mock):
            from connector_metaculus.sync import sync_user_forecasts
            results = await sync_user_forecasts(user_id="user-1", metaculus_user_id=5)

        assert len(results) == 2

    @pytest.mark.asyncio
    async def test_client_get_user_posts_follows_next_links(self):
        """MetaculusClient.get_user_posts follows `next` URLs until exhausted."""
        import json

        page1_body = {
            "count": 2,
            "next": "https://www.metaculus.com/api/posts/?forecaster_id=5&limit=100&offset=100",
            "previous": None,
            "results": [BINARY_POST_RESOLVED],
        }
        page2_body = {
            "count": 2,
            "next": None,
            "previous": "https://www.metaculus.com/api/posts/?forecaster_id=5&limit=100",
            "results": [BINARY_POST_OPEN],
        }

        # Mock the httpx.AsyncClient at the module level to avoid the sandbox SOCKS proxy
        call_count = 0
        pages = [page1_body, page2_body]

        async def mock_get(url, **kwargs):
            nonlocal call_count
            mock_resp = MagicMock()
            mock_resp.raise_for_status = MagicMock()
            mock_resp.json = MagicMock(return_value=pages[call_count])
            call_count += 1
            return mock_resp

        mock_http_instance = AsyncMock()
        mock_http_instance.get = mock_get
        mock_http_instance.__aenter__ = AsyncMock(return_value=mock_http_instance)
        mock_http_instance.__aexit__ = AsyncMock(return_value=False)
        mock_http_cls = MagicMock(return_value=mock_http_instance)

        with patch("connector_metaculus.client.httpx.AsyncClient", mock_http_cls):
            from connector_metaculus.client import MetaculusClient
            client = MetaculusClient(token="test-token")
            results = await client.get_user_posts(5)

        assert len(results) == 2
        assert call_count == 2   # two HTTP calls made
        assert results[0]["id"] == BINARY_POST_RESOLVED["id"]
        assert results[1]["id"] == BINARY_POST_OPEN["id"]

    @pytest.mark.asyncio
    async def test_client_single_page_makes_one_request(self):
        """When `next` is None, only one HTTP request is made."""
        page_body = {
            "count": 1,
            "next": None,
            "previous": None,
            "results": [BINARY_POST_OPEN],
        }

        call_count = 0

        async def mock_get(url, **kwargs):
            nonlocal call_count
            call_count += 1
            mock_resp = MagicMock()
            mock_resp.raise_for_status = MagicMock()
            mock_resp.json = MagicMock(return_value=page_body)
            return mock_resp

        mock_http_instance = AsyncMock()
        mock_http_instance.get = mock_get
        mock_http_instance.__aenter__ = AsyncMock(return_value=mock_http_instance)
        mock_http_instance.__aexit__ = AsyncMock(return_value=False)
        mock_http_cls = MagicMock(return_value=mock_http_instance)

        with patch("connector_metaculus.client.httpx.AsyncClient", mock_http_cls):
            from connector_metaculus.client import MetaculusClient
            client = MetaculusClient(token="test-token")
            results = await client.get_user_posts(5)

        assert call_count == 1
        assert len(results) == 1

    @pytest.mark.asyncio
    async def test_client_empty_results_returns_empty_list(self):
        page_body = {"count": 0, "next": None, "previous": None, "results": []}

        async def mock_get(url, **kwargs):
            mock_resp = MagicMock()
            mock_resp.raise_for_status = MagicMock()
            mock_resp.json = MagicMock(return_value=page_body)
            return mock_resp

        mock_http_instance = AsyncMock()
        mock_http_instance.get = mock_get
        mock_http_instance.__aenter__ = AsyncMock(return_value=mock_http_instance)
        mock_http_instance.__aexit__ = AsyncMock(return_value=False)
        mock_http_cls = MagicMock(return_value=mock_http_instance)

        with patch("connector_metaculus.client.httpx.AsyncClient", mock_http_cls):
            from connector_metaculus.client import MetaculusClient
            client = MetaculusClient(token="test-token")
            results = await client.get_user_posts(5)

        assert results == []
