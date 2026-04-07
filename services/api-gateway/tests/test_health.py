"""Smoke test: verify the gateway starts and /health responds."""

import pytest
from httpx import AsyncClient, ASGITransport
from api_gateway.app import create_app


@pytest.mark.asyncio
async def test_health_endpoint():
    app = create_app()
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.get("/health")
    assert resp.status_code == 200
    assert resp.json() == {"status": "ok"}
