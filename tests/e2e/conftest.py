"""
End-to-end test fixtures.

E2E tests exercise full user flows via the API gateway, with a real DB
and mocked external exchange APIs.

Setup:
  - Requires the full stack running (use docker-compose, TODO)
  - API_BASE_URL env var points at the running gateway
"""

import os
import pytest
import httpx

API_BASE_URL = os.environ.get("API_BASE_URL", "http://localhost:8000")


@pytest.fixture
def api_client() -> httpx.Client:
    """Synchronous httpx client pointed at the running gateway."""
    with httpx.Client(base_url=API_BASE_URL, timeout=10.0) as client:
        yield client
