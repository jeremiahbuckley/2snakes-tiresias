# Refresh Data Button Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a "Refresh data" button to the dashboard header that fires a background sync and polls until `last_synced_at` advances, showing per-platform errors on partial failure.

**Architecture:** Two new nullable columns on `linked_accounts` (`last_synced_at`, `last_sync_error`) are written by `sync_one_user` after each platform attempt. A new `POST /users/{user_id}/sync` endpoint in the api-gateway triggers the sync via FastAPI `BackgroundTasks` and returns 202 immediately. The dashboard response grows two fields (`last_synced_at`, `sync_status`). The Svelte component polls `getDashboard` every 3 seconds and calls `invalidateAll()` when `last_synced_at` advances.

**Tech Stack:** Python 3.12 / FastAPI / SQLAlchemy async / Alembic (backend); SvelteKit 2 / Svelte 4 (frontend); pytest-asyncio + httpx for endpoint tests; Playwright for contract tests.

---

## File Map

| File | Action |
|------|--------|
| `services/data-layer/alembic/versions/0007_linked_account_sync_status.py` | Create — migration |
| `services/data-layer/data/models/linked_account.py` | Modify — add two columns |
| `services/scheduler/scheduler/sync.py` | Modify — write sync status per platform |
| `services/scheduler/tests/test_sync.py` | Create — unit tests for status writing |
| `services/api-gateway/api_gateway/data_queries.py` | Modify — `_get_sync_status` helper + dashboard response |
| `services/api-gateway/tests/test_data_queries.py` | Modify — tests for `_get_sync_status` |
| `services/api-gateway/api_gateway/router.py` | Modify — `POST /users/{user_id}/sync` endpoint |
| `services/api-gateway/tests/test_sync_endpoint.py` | Create — endpoint tests |
| `tests/ui-shared/mock-api-server.mjs` | Modify — add sync route |
| `tests/ui-shared/api-mocks/responses/dashboard.json` | Modify — add `last_synced_at`, `sync_status` |
| `apps/user-dashboard/src/lib/api.js` | Modify — add `triggerSync` |
| `apps/user-dashboard/src/routes/dashboard/+page.server.js` | Modify — expose `token` and `lastSyncedAt` |
| `apps/user-dashboard/src/routes/dashboard/+page.svelte` | Modify — Refresh button, polling, error banner |
| `apps/user-dashboard/tests/contract/dashboard.spec.ts` | Modify — contract tests for button |

---

## Task 1: Alembic migration — add sync status columns to `linked_accounts`

**Files:**
- Create: `services/data-layer/alembic/versions/0007_linked_account_sync_status.py`

---

- [ ] **Step 1: Create the migration file**

```python
"""Add last_synced_at and last_sync_error to linked_accounts

Revision ID: 0007
Revises: 0006
Create Date: 2026-04-30
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0007"
down_revision: Union[str, None] = "0006"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "linked_accounts",
        sa.Column("last_synced_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.add_column(
        "linked_accounts",
        sa.Column("last_sync_error", sa.Text(), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("linked_accounts", "last_sync_error")
    op.drop_column("linked_accounts", "last_synced_at")
```

- [ ] **Step 2: Apply the migration**

```bash
cd services/data-layer && alembic upgrade head
```

Expected output includes: `Running upgrade 0006 -> 0007`

- [ ] **Step 3: Verify columns exist**

```bash
cd services/data-layer && python3 -c "
import asyncio, os
os.environ.setdefault('DATABASE_URL', 'postgresql+asyncpg://postgres:postgres@localhost:5432/tiresias?ssl=disable')
from sqlalchemy.ext.asyncio import create_async_engine
from sqlalchemy import text
async def check():
    engine = create_async_engine(os.environ['DATABASE_URL'])
    async with engine.connect() as conn:
        result = await conn.execute(text(\"SELECT column_name FROM information_schema.columns WHERE table_name='linked_accounts' ORDER BY ordinal_position\"))
        for row in result: print(row[0])
asyncio.run(check())
"
```

Expected output includes `last_synced_at` and `last_sync_error`.

- [ ] **Step 4: Commit**

```bash
git add services/data-layer/alembic/versions/0007_linked_account_sync_status.py
git commit -m "feat: migration 0007 — add last_synced_at and last_sync_error to linked_accounts"
```

---

## Task 2: Update LinkedAccount ORM model

**Files:**
- Modify: `services/data-layer/data/models/linked_account.py`

---

- [ ] **Step 1: Add the two columns to the ORM model**

In `services/data-layer/data/models/linked_account.py`, add `datetime` to the imports at the top:

```python
from datetime import datetime
```

Add this import to the SQLAlchemy block (alongside `Boolean`, `ForeignKey`, etc.):

```python
from sqlalchemy import Boolean, DateTime, ForeignKey, String, Text, UniqueConstraint
```

Add these two mapped columns to the `LinkedAccount` class body, after the `is_verified` column:

```python
    last_synced_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    last_sync_error: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
```

- [ ] **Step 2: Commit**

```bash
git add services/data-layer/data/models/linked_account.py
git commit -m "feat: add last_synced_at and last_sync_error to LinkedAccount model"
```

---

## Task 3: Write sync status after each platform attempt in scheduler

**Files:**
- Modify: `services/scheduler/scheduler/sync.py`
- Create: `services/scheduler/tests/test_sync.py`

---

- [ ] **Step 1: Write the failing tests**

Create `services/scheduler/tests/test_sync.py`:

```python
"""Unit tests for sync_one_user sync status writing."""
from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest


def _make_account(platform: str = "kalshi", user_id=None) -> MagicMock:
    acct = MagicMock()
    acct.platform = platform
    acct.user_id = user_id or uuid4()
    acct.is_enabled = True
    acct.is_verified = True
    acct.last_synced_at = None
    acct.last_sync_error = None
    return acct


def _make_db(accounts: list) -> AsyncMock:
    mock_result = MagicMock()
    mock_result.scalars.return_value.all.return_value = accounts
    db = AsyncMock()
    db.execute = AsyncMock(return_value=mock_result)
    return db


@pytest.mark.asyncio
async def test_sync_one_user_sets_last_synced_at_on_success():
    user_id = uuid4()
    account = _make_account("kalshi", user_id)
    db = _make_db([account])

    with patch("scheduler.sync._sync_kalshi", new=AsyncMock(return_value=3)):
        from scheduler.sync import sync_one_user
        total = await sync_one_user(db, user_id)

    assert account.last_synced_at is not None
    assert account.last_sync_error is None
    assert total == 3


@pytest.mark.asyncio
async def test_sync_one_user_sets_last_sync_error_on_failure():
    user_id = uuid4()
    account = _make_account("manifold", user_id)
    db = _make_db([account])

    with patch("scheduler.sync._sync_manifold", new=AsyncMock(side_effect=RuntimeError("API timeout"))):
        from scheduler.sync import sync_one_user
        total = await sync_one_user(db, user_id)

    assert account.last_synced_at is not None
    assert account.last_sync_error == "API timeout"
    assert total == 0


@pytest.mark.asyncio
async def test_sync_one_user_partial_success():
    """One platform succeeds, one fails — both get last_synced_at set."""
    user_id = uuid4()
    kalshi_account = _make_account("kalshi", user_id)
    manifold_account = _make_account("manifold", user_id)
    db = _make_db([kalshi_account, manifold_account])

    with patch("scheduler.sync._sync_kalshi", new=AsyncMock(return_value=5)), \
         patch("scheduler.sync._sync_manifold", new=AsyncMock(side_effect=RuntimeError("timeout"))):
        from scheduler.sync import sync_one_user
        total = await sync_one_user(db, user_id)

    assert kalshi_account.last_synced_at is not None
    assert kalshi_account.last_sync_error is None
    assert manifold_account.last_synced_at is not None
    assert manifold_account.last_sync_error == "timeout"
    assert total == 5
```

- [ ] **Step 2: Run the tests to confirm they fail**

```bash
cd /Users/jbuckley/Documents/code/2snakes-scratch && .venv/bin/pytest services/scheduler/tests/test_sync.py -v
```

Expected: FAIL — `AttributeError` (last_synced_at not set on account).

- [ ] **Step 3: Add the sync status writes to sync_one_user**

In `services/scheduler/scheduler/sync.py`, add to the imports at the top:

```python
from datetime import datetime, timezone
```

In `sync_one_user`, find the per-platform dispatch loop. It currently looks like:

```python
        try:
            if platform == Platform.KALSHI:
                count = await _sync_kalshi(db, account)
            elif platform == Platform.MANIFOLD:
                count = await _sync_manifold(db, account)
            elif platform == Platform.METACULUS:
                count = await _sync_metaculus(db, account)
            elif platform == Platform.POLYMARKET:
                count = await _sync_polymarket(db, account)
            else:
                logger.warning("Unknown market platform %r — skipping", platform)
                count = 0

            logger.info(
                "Synced %d predictions from %s for user %s", count, platform, user_id
            )
            total += count

        except Exception as exc:
            logger.error(
                "Error syncing %s for user %s: %s", platform, user_id, exc, exc_info=True
            )
```

Replace with:

```python
        try:
            if platform == Platform.KALSHI:
                count = await _sync_kalshi(db, account)
            elif platform == Platform.MANIFOLD:
                count = await _sync_manifold(db, account)
            elif platform == Platform.METACULUS:
                count = await _sync_metaculus(db, account)
            elif platform == Platform.POLYMARKET:
                count = await _sync_polymarket(db, account)
            else:
                logger.warning("Unknown market platform %r — skipping", platform)
                count = 0

            account.last_synced_at = datetime.now(timezone.utc)
            account.last_sync_error = None
            logger.info(
                "Synced %d predictions from %s for user %s", count, platform, user_id
            )
            total += count

        except Exception as exc:
            account.last_sync_error = str(exc)
            account.last_synced_at = datetime.now(timezone.utc)
            logger.error(
                "Error syncing %s for user %s: %s", platform, user_id, exc, exc_info=True
            )
```

- [ ] **Step 4: Run the tests to confirm they pass**

```bash
cd /Users/jbuckley/Documents/code/2snakes-scratch && .venv/bin/pytest services/scheduler/tests/test_sync.py -v
```

Expected: 3 tests PASS.

- [ ] **Step 5: Commit**

```bash
git add services/scheduler/scheduler/sync.py services/scheduler/tests/test_sync.py
git commit -m "feat: write last_synced_at and last_sync_error to linked_account after each platform sync"
```

---

## Task 4: Add sync status to dashboard query response

**Files:**
- Modify: `services/api-gateway/api_gateway/data_queries.py`
- Modify: `services/api-gateway/tests/test_data_queries.py`

---

- [ ] **Step 1: Write the failing test**

In `services/api-gateway/tests/test_data_queries.py`, add at the end of the file:

```python
# ── _get_sync_status ──────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_get_sync_status_returns_last_synced_at_as_max():
    from unittest.mock import AsyncMock, MagicMock
    from datetime import datetime, timezone
    from uuid import uuid4
    from api_gateway.data_queries import _get_sync_status

    user_id = uuid4()

    account1 = MagicMock()
    account1.platform = "kalshi"
    account1.last_synced_at = datetime(2026, 4, 30, 12, 0, 0, tzinfo=timezone.utc)
    account1.last_sync_error = None

    account2 = MagicMock()
    account2.platform = "manifold"
    account2.last_synced_at = datetime(2026, 4, 30, 11, 0, 0, tzinfo=timezone.utc)
    account2.last_sync_error = "API timeout"

    mock_result = MagicMock()
    mock_result.scalars.return_value.all.return_value = [account1, account2]
    mock_session = AsyncMock()
    mock_session.execute = AsyncMock(return_value=mock_result)

    result = await _get_sync_status(user_id, mock_session)

    assert result["last_synced_at"] == "2026-04-30T12:00:00+00:00"
    assert len(result["sync_status"]) == 2

    kalshi = next(s for s in result["sync_status"] if s["platform"] == "kalshi")
    assert kalshi["error"] is None

    manifold = next(s for s in result["sync_status"] if s["platform"] == "manifold")
    assert manifold["error"] == "API timeout"


@pytest.mark.asyncio
async def test_get_sync_status_returns_none_when_no_accounts_synced():
    from unittest.mock import AsyncMock, MagicMock
    from uuid import uuid4
    from api_gateway.data_queries import _get_sync_status

    user_id = uuid4()

    account = MagicMock()
    account.platform = "kalshi"
    account.last_synced_at = None
    account.last_sync_error = None

    mock_result = MagicMock()
    mock_result.scalars.return_value.all.return_value = [account]
    mock_session = AsyncMock()
    mock_session.execute = AsyncMock(return_value=mock_result)

    result = await _get_sync_status(user_id, mock_session)

    assert result["last_synced_at"] is None
    assert result["sync_status"] == [{"platform": "kalshi", "last_synced_at": None, "error": None}]
```

- [ ] **Step 2: Run to confirm they fail**

```bash
cd /Users/jbuckley/Documents/code/2snakes-scratch && .venv/bin/pytest services/api-gateway/tests/test_data_queries.py::test_get_sync_status_returns_last_synced_at_as_max services/api-gateway/tests/test_data_queries.py::test_get_sync_status_returns_none_when_no_accounts_synced -v
```

Expected: FAIL — `ImportError: cannot import name '_get_sync_status'`.

- [ ] **Step 3: Add `_get_sync_status` helper to data_queries.py**

In `services/api-gateway/api_gateway/data_queries.py`, add `LinkedAccount` and `MARKET_PLATFORMS` to the imports:

```python
from data.models.linked_account import LinkedAccount, MARKET_PLATFORMS
```

Add this function after the `_user_tags` function:

```python
async def _get_sync_status(user_id: UUID, session: AsyncSession) -> dict:
    """Return last_synced_at (max across platforms) and per-platform sync_status."""
    result = await session.execute(
        select(LinkedAccount).where(
            LinkedAccount.user_id == user_id,
            LinkedAccount.platform.in_([p.value for p in MARKET_PLATFORMS]),
        )
    )
    accounts = result.scalars().all()
    sync_status = [
        {
            "platform": a.platform,
            "last_synced_at": a.last_synced_at.isoformat() if a.last_synced_at else None,
            "error": a.last_sync_error,
        }
        for a in accounts
    ]
    timestamps = [a.last_synced_at for a in accounts if a.last_synced_at]
    last_synced_at = max(timestamps).isoformat() if timestamps else None
    return {"last_synced_at": last_synced_at, "sync_status": sync_status}
```

- [ ] **Step 4: Add `_get_sync_status` call to `get_dashboard_data`**

In `get_dashboard_data`, both the tag-filtered and unfiltered branches return a dict. In each `return { ... }` statement, add the two new fields.

**Tag-filtered branch** — replace:

```python
        return {
            'user': user_dict,
            'score': _compute_score_from_predictions(all_preds),
            'badges': [],
            'recent_predictions': [_pred_dict(p) for p in recent],
            'available_tags': available_tags,
        }
```

With:

```python
        sync_info = await _get_sync_status(user_id, session)
        return {
            'user': user_dict,
            'score': _compute_score_from_predictions(all_preds),
            'badges': [],
            'recent_predictions': [_pred_dict(p) for p in recent],
            'available_tags': available_tags,
            'last_synced_at': sync_info['last_synced_at'],
            'sync_status': sync_info['sync_status'],
        }
```

**Unfiltered branch** — replace:

```python
    return {
        'user': user_dict,
        'score': score_data,
        'badges': badges,
        'recent_predictions': [_pred_dict(p) for p in recent],
        'available_tags': available_tags,
    }
```

With:

```python
    sync_info = await _get_sync_status(user_id, session)
    return {
        'user': user_dict,
        'score': score_data,
        'badges': badges,
        'recent_predictions': [_pred_dict(p) for p in recent],
        'available_tags': available_tags,
        'last_synced_at': sync_info['last_synced_at'],
        'sync_status': sync_info['sync_status'],
    }
```

- [ ] **Step 5: Run the new tests to confirm they pass**

```bash
cd /Users/jbuckley/Documents/code/2snakes-scratch && .venv/bin/pytest services/api-gateway/tests/test_data_queries.py -v
```

Expected: all tests PASS including the two new ones.

- [ ] **Step 6: Commit**

```bash
git add services/api-gateway/api_gateway/data_queries.py services/api-gateway/tests/test_data_queries.py
git commit -m "feat: add _get_sync_status helper and include last_synced_at/sync_status in dashboard response"
```

---

## Task 5: Add POST /users/{user_id}/sync endpoint

**Files:**
- Modify: `services/api-gateway/api_gateway/router.py`
- Create: `services/api-gateway/tests/test_sync_endpoint.py`

Note: `router.py` imports `sync_one_user` from `scheduler.sync`. This works in the shared monorepo `.venv` (all packages installed). The api-gateway Docker image will need connector packages added before multi-container deployment — out of scope for this feature.

---

- [ ] **Step 1: Write the failing tests**

Create `services/api-gateway/tests/test_sync_endpoint.py`:

```python
"""Tests for POST /users/{user_id}/sync endpoint."""
from __future__ import annotations

from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest
from httpx import ASGITransport, AsyncClient

from api_gateway.app import app
from auth_service.api import get_current_user
from data.database import get_db


def _make_user(user_id=None):
    user = MagicMock()
    user.id = user_id or uuid4()
    return user


def _make_db(scalar_value=None):
    """Return a mock AsyncSession where the rate-limit query returns scalar_value."""
    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = scalar_value
    db = AsyncMock()
    db.execute = AsyncMock(return_value=mock_result)
    return db


@pytest.mark.asyncio
async def test_trigger_sync_returns_202():
    user_id = uuid4()
    app.dependency_overrides[get_current_user] = lambda: _make_user(user_id)
    app.dependency_overrides[get_db] = lambda: _make_db(scalar_value=None)
    try:
        with patch("api_gateway.router._background_sync", new=AsyncMock()):
            async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
                response = await client.post(f"/users/{user_id}/sync")
        assert response.status_code == 202
        assert response.json() == {"status": "syncing"}
    finally:
        app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_trigger_sync_returns_403_for_wrong_user():
    user_id = uuid4()
    other_user_id = uuid4()
    app.dependency_overrides[get_current_user] = lambda: _make_user(other_user_id)
    app.dependency_overrides[get_db] = lambda: _make_db()
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.post(f"/users/{user_id}/sync")
        assert response.status_code == 403
    finally:
        app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_trigger_sync_returns_429_when_rate_limited():
    user_id = uuid4()
    recent_ts = datetime.now(timezone.utc)
    app.dependency_overrides[get_current_user] = lambda: _make_user(user_id)
    app.dependency_overrides[get_db] = lambda: _make_db(scalar_value=recent_ts)
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.post(f"/users/{user_id}/sync")
        assert response.status_code == 429
        assert "too recently" in response.json()["detail"]
    finally:
        app.dependency_overrides.clear()
```

- [ ] **Step 2: Run to confirm they fail**

```bash
cd /Users/jbuckley/Documents/code/2snakes-scratch && .venv/bin/pytest services/api-gateway/tests/test_sync_endpoint.py -v
```

Expected: FAIL — `404 Not Found` (endpoint doesn't exist yet).

- [ ] **Step 3: Add the endpoint and background function to router.py**

In `services/api-gateway/api_gateway/router.py`, add to the imports:

```python
from datetime import datetime, timezone, timedelta

from fastapi import BackgroundTasks

from data.database import db_context
from data.models.linked_account import LinkedAccount
```

Add the background function above the router declarations (before `router = APIRouter()`):

```python
async def _background_sync(user_id) -> None:
    from scheduler.sync import sync_one_user
    async with db_context() as db:
        await sync_one_user(db, user_id)
```

Add the endpoint at the end of the file:

```python
@router.post("/users/{user_id}/sync", status_code=202)
async def trigger_user_sync(
    user_id: str,
    background_tasks: BackgroundTasks,
    current_user: CurrentUser,
    db: DB,
) -> dict:
    if user_id != str(current_user.id):
        raise HTTPException(status_code=403)

    rate_limit_cutoff = datetime.now(timezone.utc) - timedelta(seconds=60)
    recent = await db.execute(
        select(LinkedAccount.last_synced_at).where(
            LinkedAccount.user_id == current_user.id,
            LinkedAccount.last_synced_at > rate_limit_cutoff,
        ).limit(1)
    )
    if recent.scalar_one_or_none() is not None:
        raise HTTPException(status_code=429, detail="Sync triggered too recently, please wait")

    background_tasks.add_task(_background_sync, current_user.id)
    return {"status": "syncing"}
```

Add a new import line to router.py alongside the other imports at the top of the file:

```python
from sqlalchemy import select
```

(router.py has no existing `sqlalchemy` import — only `sqlalchemy.ext.asyncio`. This is a new line.)

- [ ] **Step 4: Run the tests to confirm they pass**

```bash
cd /Users/jbuckley/Documents/code/2snakes-scratch && .venv/bin/pytest services/api-gateway/tests/test_sync_endpoint.py -v
```

Expected: 3 tests PASS.

- [ ] **Step 5: Commit**

```bash
git add services/api-gateway/api_gateway/router.py services/api-gateway/tests/test_sync_endpoint.py
git commit -m "feat: add POST /users/{user_id}/sync endpoint with rate limiting and background sync"
```

---

## Task 6: Frontend data plumbing — api.js, mock server, dashboard fixture, page server

**Files:**
- Modify: `apps/user-dashboard/src/lib/api.js`
- Modify: `tests/ui-shared/mock-api-server.mjs`
- Modify: `tests/ui-shared/api-mocks/responses/dashboard.json`
- Modify: `apps/user-dashboard/src/routes/dashboard/+page.server.js`

---

- [ ] **Step 1: Add `triggerSync` to api.js**

In `apps/user-dashboard/src/lib/api.js`, add this function after `getUserStats`:

```js
// ---------------------------------------------------------------------------
// Sync trigger  —  POST /users/{user_id}/sync
// ---------------------------------------------------------------------------

/**
 * Trigger an on-demand background sync for the authenticated user.
 * Returns 202 immediately; poll getDashboard to detect completion.
 */
export async function triggerSync(userId, token) {
  return apiFetch(`/users/${userId}/sync`, { method: 'POST', token });
}
```

- [ ] **Step 2: Add the sync route to the mock server**

In `tests/ui-shared/mock-api-server.mjs`, add to the `routes` object (after the `stats` entry):

```js
  'POST /users/:userId/sync':        JSON.stringify({ status: 'syncing' }),
```

The `matchRoute` function already handles `:userId` patterns, so this is all that's needed.

- [ ] **Step 3: Add `last_synced_at` and `sync_status` to the dashboard fixture**

In `tests/ui-shared/api-mocks/responses/dashboard.json`, add two top-level fields after `"available_tags"`:

```json
  "last_synced_at": "2026-04-01T00:00:00Z",
  "sync_status": [
    { "platform": "kalshi",    "last_synced_at": "2026-04-01T00:00:00Z", "error": null },
    { "platform": "polymarket","last_synced_at": "2026-04-01T00:00:00Z", "error": null },
    { "platform": "manifold",  "last_synced_at": "2026-04-01T00:00:00Z", "error": null },
    { "platform": "metaculus", "last_synced_at": "2026-04-01T00:00:00Z", "error": null }
  ],
```

Keep `"last_synced_at"` identical to the `score.last_scored_at` date (`"2026-04-01T00:00:00Z"`) so the polling comparison never triggers during contract tests (baseline and polled value are the same).

- [ ] **Step 4: Expose `token` and `lastSyncedAt` in the load function**

In `apps/user-dashboard/src/routes/dashboard/+page.server.js`, update both the mock branch and the real-data branch to expose `token` and `lastSyncedAt`:

Replace the entire file with:

```js
import { getDashboard } from '$lib/api.js';

/** @type {import('./$types').PageServerLoad} */
export async function load({ parent, url }) {
  const { user, token, isMockSession } = await parent();
  const tag = url.searchParams.get('tag') ?? '';
  if (isMockSession) {
    return {
      user,
      token,
      score: { total_predictions: 0, resolved_predictions: 0, mean_brier_score: null, brier_skill_score: null, calibration_score: null, accuracy: null, last_scored_at: null, per_source: {}, per_domain: {} },
      badges: [],
      recentPredictions: [],
      availableTags: ['politics', 'crypto'],
      tagFilter: tag,
      lastSyncedAt: null,
      syncStatus: [],
    };
  }
  const data = await getDashboard(user.id, token, { tag });
  return {
    user: data.user,
    token,
    score: data.score,
    badges: data.badges,
    recentPredictions: data.recent_predictions,
    availableTags: data.available_tags ?? [],
    tagFilter: tag,
    lastSyncedAt: data.last_synced_at ?? null,
    syncStatus: data.sync_status ?? [],
  };
}
```

- [ ] **Step 5: Commit**

```bash
git add apps/user-dashboard/src/lib/api.js \
        tests/ui-shared/mock-api-server.mjs \
        "tests/ui-shared/api-mocks/responses/dashboard.json" \
        apps/user-dashboard/src/routes/dashboard/+page.server.js
git commit -m "feat: wire triggerSync in api.js, add sync fields to mock server and dashboard fixture"
```

---

## Task 7: Refresh button, polling, and error banner in +page.svelte

**Files:**
- Modify: `apps/user-dashboard/src/routes/dashboard/+page.svelte`
- Modify: `apps/user-dashboard/tests/contract/dashboard.spec.ts`

---

- [ ] **Step 1: Write the failing contract tests**

In `apps/user-dashboard/tests/contract/dashboard.spec.ts`, add after the last existing test:

```ts
  contractTest('refresh data button is visible in dashboard header', async ({ authedPage: page }) => {
    await page.goto('/dashboard');
    await page.waitForLoadState('networkidle');
    await expect(page.getByRole('button', { name: /refresh data/i })).toBeVisible();
  });

  contractTest('clicking refresh button shows syncing state', async ({ authedPage: page }) => {
    await page.goto('/dashboard');
    await page.waitForLoadState('networkidle');
    await page.getByRole('button', { name: /refresh data/i }).click();
    await expect(page.getByRole('button', { name: /syncing/i })).toBeVisible();
    await expect(page.getByRole('button', { name: /syncing/i })).toBeDisabled();
  });
```

- [ ] **Step 2: Run to confirm they fail**

```bash
cd apps/user-dashboard && npm run test:contract -- --grep "refresh data"
```

Expected: FAIL — button not found.

- [ ] **Step 3: Update the script section of +page.svelte**

In `apps/user-dashboard/src/routes/dashboard/+page.svelte`, replace the entire `<script>` block with:

```svelte
<script>
  import { goto } from '$app/navigation';
  import { invalidateAll } from '$app/navigation';
  import { onDestroy } from 'svelte';
  import TagFilter from '$lib/components/TagFilter.svelte';
  import { triggerSync, getDashboard } from '$lib/api.js';

  /** @type {import('./$types').PageData} */
  export let data;

  // Make page data reactive so invalidateAll() refreshes the display.
  $: user = data.user;
  $: score = data.score;
  $: badges = data.badges;
  $: recentPredictions = data.recentPredictions;
  $: tagFilter = data.tagFilter ?? '';
  $: availableTags = data.availableTags ?? [];

  $: earnedBadges = badges.filter((b) => b.earned);
  $: lockedBadges = badges.filter((b) => !b.earned);
  $: resolutionRate = score.total_predictions
    ? ((score.resolved_predictions / score.total_predictions) * 100).toFixed(0)
    : 0;
  $: noScoringData = score.mean_brier_score == null;
  $: perSource = Object.entries(score.per_source ?? {});

  // Refresh button state
  let syncing = false;
  let syncDisabled = false;
  let syncErrors = [];
  let _pollTimer;

  async function onRefresh() {
    if (syncing || syncDisabled) return;
    syncing = true;
    syncDisabled = true;
    syncErrors = [];

    const baselineSyncedAt = data.lastSyncedAt;

    // Client-side rate limit: re-enable button after 30s regardless of outcome.
    setTimeout(() => { syncDisabled = false; }, 30_000);

    try {
      await triggerSync(user.id, data.token);
    } catch (_) {
      syncing = false;
      return;
    }

    // Poll every 3s until last_synced_at advances or 90s elapses.
    const deadline = Date.now() + 90_000;
    _pollTimer = setInterval(async () => {
      if (Date.now() > deadline) {
        clearInterval(_pollTimer);
        syncing = false;
        return;
      }
      try {
        const result = await getDashboard(user.id, data.token);
        if (result.last_synced_at && result.last_synced_at !== baselineSyncedAt) {
          clearInterval(_pollTimer);
          syncErrors = (result.sync_status ?? [])
            .filter((s) => s.error)
            .map((s) => `${s.platform} returned an error`);
          await invalidateAll();
          syncing = false;
        }
      } catch (_) {
        // ignore transient poll errors
      }
    }, 3_000);
  }

  onDestroy(() => {
    if (_pollTimer) clearInterval(_pollTimer);
  });

  function onTagChange(e) {
    const tag = e.detail;
    const params = new URLSearchParams();
    if (tag) params.set('tag', tag);
    const qs = params.toString();
    goto(`/dashboard${qs ? '?' + qs : ''}`, { replaceState: true });
  }

  function fmt(n, decimals = 3) {
    return n == null ? '—' : n.toFixed(decimals);
  }

  function fmtPct(n) {
    return n == null ? '—' : `${(n * 100).toFixed(1)}%`;
  }

  function fmtDate(iso) {
    if (!iso) return '—';
    return new Date(iso).toLocaleDateString('en-US', { month: 'short', day: 'numeric', year: 'numeric' });
  }

  const platformColors = {
    kalshi: '#00b894',
    polymarket: '#6c5ce7',
    manifold: '#e17055',
    metaculus: '#0984e3',
  };

  function sourceColor(source) {
    return platformColors[source] ?? '#aaa';
  }
</script>
```

- [ ] **Step 4: Update the header HTML to add the Refresh button**

In `apps/user-dashboard/src/routes/dashboard/+page.svelte`, replace the `<div class="page-header">` block:

```svelte
<div class="page-header">
  <div>
    <h1>Dashboard</h1>
    <p class="welcome">Welcome back, {user.display_name ?? user.username}</p>
  </div>
  {#if score.last_scored_at}
    <div class="last-scored">Last scored: {fmtDate(score.last_scored_at)}</div>
  {/if}
</div>
```

With:

```svelte
<div class="page-header">
  <div>
    <h1>Dashboard</h1>
    <p class="welcome">Welcome back, {user.display_name ?? user.username}</p>
  </div>
  <div class="header-right">
    {#if score.last_scored_at}
      <div class="last-scored">Last scored: {fmtDate(score.last_scored_at)}</div>
    {/if}
    <button
      class="refresh-btn"
      class:syncing
      disabled={syncing || syncDisabled}
      on:click={onRefresh}
      aria-label="Refresh prediction data"
    >
      {#if syncing}
        <span class="spinner" aria-hidden="true"></span>
        Syncing…
      {:else}
        Refresh data
      {/if}
    </button>
  </div>
</div>
```

- [ ] **Step 5: Add the error banner after `<div class="page-controls">`**

After the closing `</div>` of `.page-controls`, add:

```svelte
{#if syncErrors.length > 0}
  <div class="sync-warning" role="alert">
    <strong>Sync complete</strong> — {syncErrors.join('; ')}
    <button class="dismiss-btn" on:click={() => syncErrors = []} aria-label="Dismiss">×</button>
  </div>
{/if}
```

- [ ] **Step 6: Add styles for the new elements**

In the `<style>` block of `+page.svelte`, add after the existing `.last-scored` rule:

```css
  .header-right {
    display: flex;
    flex-direction: column;
    align-items: flex-end;
    gap: 8px;
  }

  .refresh-btn {
    display: inline-flex;
    align-items: center;
    gap: 6px;
    background: #4f8ef7;
    color: white;
    border: none;
    border-radius: 8px;
    padding: 7px 14px;
    font-size: 13px;
    font-weight: 600;
    cursor: pointer;
    transition: background 0.15s;
  }

  .refresh-btn:hover:not(:disabled) {
    background: #3b7de8;
  }

  .refresh-btn:disabled {
    opacity: 0.6;
    cursor: not-allowed;
  }

  .spinner {
    display: inline-block;
    width: 12px;
    height: 12px;
    border: 2px solid rgba(255, 255, 255, 0.4);
    border-top-color: white;
    border-radius: 50%;
    animation: spin 0.7s linear infinite;
    flex-shrink: 0;
  }

  @keyframes spin {
    to { transform: rotate(360deg); }
  }

  .sync-warning {
    display: flex;
    align-items: center;
    gap: 10px;
    background: #fffbeb;
    border: 1px solid #fcd34d;
    border-radius: 10px;
    padding: 12px 16px;
    font-size: 14px;
    color: #92400e;
    margin-bottom: 16px;
  }

  .dismiss-btn {
    margin-left: auto;
    background: none;
    border: none;
    cursor: pointer;
    font-size: 18px;
    color: #92400e;
    line-height: 1;
    padding: 0 2px;
  }
```

- [ ] **Step 7: Run type check**

```bash
cd apps/user-dashboard && npm run check
```

Expected: zero errors.

- [ ] **Step 8: Run the contract tests**

```bash
cd apps/user-dashboard && npm run test:contract
```

Expected: all tests pass including the two new ones. Quote the full terminal output.

- [ ] **Step 9: Commit**

```bash
git add apps/user-dashboard/src/routes/dashboard/+page.svelte \
        apps/user-dashboard/tests/contract/dashboard.spec.ts
git commit -m "feat: add Refresh data button with background sync polling and partial-failure banner"
```

---

## Verification

After all tasks are complete, run the full test suite:

```bash
cd /Users/jbuckley/Documents/code/2snakes-scratch
.venv/bin/pytest services/connector-kalshi/tests/ services/scheduler/tests/ services/api-gateway/tests/ -v
cd apps/user-dashboard && npm run check && npm run test:contract
```

All tests should pass.
