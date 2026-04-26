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
        """MetaculusClient.get_user_posts follows `next` URLs until exhausted.

        A full first page (100 results) triggers pagination; a partial second
        page (fewer than 100) signals the end regardless of `next`.
        """
        # Page 1: full page of 100 identical posts → client must fetch page 2
        page1_body = {
            "count": 101,
            "next": "https://www.metaculus.com/api/posts/?forecaster_id=5&limit=100&offset=100",
            "previous": None,
            "results": [BINARY_POST_RESOLVED] * 100,
        }
        # Page 2: 1 post → partial page signals end of results
        page2_body = {
            "count": 101,
            "next": None,
            "previous": "https://www.metaculus.com/api/posts/?forecaster_id=5&limit=100",
            "results": [BINARY_POST_OPEN],
        }

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

        assert call_count == 2
        assert len(results) == 101
        assert results[0]["id"] == BINARY_POST_RESOLVED["id"]
        assert results[-1]["id"] == BINARY_POST_OPEN["id"]

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
    async def test_client_sleeps_between_pages_to_respect_rate_limit(self):
        """A delay must be inserted between page requests to avoid 429 responses."""
        import asyncio

        # Page 1 must be full (100 results) so the client knows to fetch page 2
        page1_body = {
            "count": 101,
            "next": "https://www.metaculus.com/api/posts/?forecaster_id=5&limit=100&offset=100",
            "previous": None,
            "results": [BINARY_POST_RESOLVED] * 100,
        }
        page2_body = {
            "count": 101,
            "next": None,
            "previous": None,
            "results": [BINARY_POST_OPEN],
        }

        pages = [page1_body, page2_body]
        call_count = 0

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

        sleep_calls: list[float] = []

        async def capture_sleep(seconds: float) -> None:
            sleep_calls.append(seconds)

        with (
            patch("connector_metaculus.client.httpx.AsyncClient", mock_http_cls),
            patch("connector_metaculus.client.asyncio.sleep", capture_sleep),
        ):
            from connector_metaculus.client import MetaculusClient
            client = MetaculusClient(token="test-token")
            await client.get_user_posts(5)

        # One sleep between the two pages (not before page 1)
        assert len(sleep_calls) == 1
        assert sleep_calls[0] > 0

    @pytest.mark.asyncio
    async def test_client_stops_when_results_fewer_than_limit(self):
        """If the API returns count=0 but a `next` URL (Metaculus bug), stop when
        the result count is below the page limit rather than following next forever."""
        page1_body = {
            "count": 0,   # Metaculus API bug: count=0 even though results exist
            "next": "https://www.metaculus.com/api/posts/?forecaster_id=300060&limit=100&offset=100",
            "previous": None,
            "results": [BINARY_POST_RESOLVED, BINARY_POST_OPEN],  # 2 < 100 (limit)
        }

        call_count = 0

        async def mock_get(url, **kwargs):
            nonlocal call_count
            call_count += 1
            mock_resp = MagicMock()
            mock_resp.raise_for_status = MagicMock()
            mock_resp.json = MagicMock(return_value=page1_body)
            return mock_resp

        mock_http_instance = AsyncMock()
        mock_http_instance.get = mock_get
        mock_http_instance.__aenter__ = AsyncMock(return_value=mock_http_instance)
        mock_http_instance.__aexit__ = AsyncMock(return_value=False)
        mock_http_cls = MagicMock(return_value=mock_http_instance)

        with patch("connector_metaculus.client.httpx.AsyncClient", mock_http_cls):
            from connector_metaculus.client import MetaculusClient
            client = MetaculusClient(token="test-token")
            results = await client.get_user_posts(300060)

        # Should stop after one page despite `next` being present
        assert call_count == 1
        assert len(results) == 2

    @pytest.mark.asyncio
    async def test_client_retries_page_once_on_429(self):
        """A 429 response triggers a wait and single retry; pagination continues on success."""
        # Page 1 must be full (100 results) so the client knows to fetch page 2
        page1_body = {
            "count": 101,
            "next": "https://www.metaculus.com/api/posts/?forecaster_id=5&limit=100&offset=100",
            "previous": None,
            "results": [BINARY_POST_RESOLVED] * 100,
        }
        page2_body = {
            "count": 101,
            "next": None,
            "previous": None,
            "results": [BINARY_POST_OPEN],
        }

        import httpx as _httpx

        call_count = 0
        sleep_calls: list[float] = []

        async def mock_get(url, **kwargs):
            nonlocal call_count
            call_count += 1
            mock_resp = MagicMock()
            if call_count == 1:
                mock_resp.status_code = 200
                mock_resp.raise_for_status = MagicMock()
                mock_resp.json = MagicMock(return_value=page1_body)
            elif call_count == 2:
                # First attempt at page 2: real 429 — raise_for_status raises like httpx would
                mock_resp.status_code = 429
                req = _httpx.Request("GET", url if isinstance(url, str) else "https://example.com/")
                mock_resp.raise_for_status = MagicMock(
                    side_effect=_httpx.HTTPStatusError(
                        "429 Too Many Requests", request=req, response=mock_resp
                    )
                )
            else:
                # Retry of page 2: success
                mock_resp.status_code = 200
                mock_resp.raise_for_status = MagicMock()
                mock_resp.json = MagicMock(return_value=page2_body)
            return mock_resp

        async def capture_sleep(seconds: float) -> None:
            sleep_calls.append(seconds)

        mock_http_instance = AsyncMock()
        mock_http_instance.get = mock_get
        mock_http_instance.__aenter__ = AsyncMock(return_value=mock_http_instance)
        mock_http_instance.__aexit__ = AsyncMock(return_value=False)
        mock_http_cls = MagicMock(return_value=mock_http_instance)

        with (
            patch("connector_metaculus.client.httpx.AsyncClient", mock_http_cls),
            patch("connector_metaculus.client.asyncio.sleep", capture_sleep),
        ):
            from connector_metaculus.client import MetaculusClient
            client = MetaculusClient(token="test-token")
            results = await client.get_user_posts(5)

        # Both pages' posts are returned despite the 429 on the first attempt
        assert len(results) == 101   # 100 from page1 + 1 from page2
        assert call_count == 3   # page1, page2-429, page2-retry
        # The retry delay must be longer than the normal page-to-page delay
        assert any(s >= 60 for s in sleep_calls), f"Expected a >=60s retry sleep; got {sleep_calls}"

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
