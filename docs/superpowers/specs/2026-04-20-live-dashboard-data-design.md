# Live Dashboard Data Implementation Design

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace all hardcoded mock data in the three dashboard route loaders (`/dashboard`, `/predictions`, `/stats`) with real API calls to the api-gateway, which in turn queries Postgres via a new query layer.

**Architecture:** Page-scoped endpoints — one endpoint per dashboard page, each returning exactly what that page needs. A new `data_queries.py` module in the gateway holds all DB query logic with no FastAPI concerns, making future extraction to a data microservice mechanical. The frontend wiring follows the settings page pattern exactly.

**Tech Stack:** FastAPI, SQLAlchemy (data-layer models), SvelteKit `+page.server.js` loaders, Playwright contract tests.

---

## Architectural Notes

> **Precompute calibration and Brier timeline (future):** Calibration buckets and the Brier score monthly timeline are computed on-the-fly in `data_queries.py` by aggregating the predictions table. Once query latency becomes noticeable, these should be precomputed and stored as JSONB columns on `user_scores`, and the query functions should swap to cached reads.

> **Extract to data microservice (future):** When the number of data-work endpoints inside the gateway exceeds ~10, extract `data_queries.py` and the three data route handlers into a standalone data microservice. The gateway becomes a thin proxy; the frontend client, mock server, and contract tests are untouched.

---

## File Structure

**New files:**
- `services/api-gateway/data_queries.py` — query layer: one function per response shape, plain Python, no FastAPI

**Modified files:**
- `services/api-gateway/router.py` — replace three stubs with real handlers calling `data_queries`
- `apps/user-dashboard/src/lib/api.js` — add `getDashboard`, `getPredictions`, `getUserStats`
- `apps/user-dashboard/src/routes/dashboard/+page.server.js` — replace mock with `getDashboard` call
- `apps/user-dashboard/src/routes/predictions/+page.server.js` — replace mock with `getPredictions` call
- `apps/user-dashboard/src/routes/stats/+page.server.js` — replace mock with `getUserStats` call
- `tests/ui-shared/mock-api-server.mjs` — add three new route handlers
- `tests/ui-shared/api-mocks/responses/dashboard.json` — new mock response
- `tests/ui-shared/api-mocks/responses/predictions.json` — new mock response
- `tests/ui-shared/api-mocks/responses/stats.json` — new mock response
- `tests/contract/dashboard.spec.ts` — add mock-banner assertion
- `tests/contract/predictions.spec.ts` — verify filter params reflected in results
- `tests/contract/stats.spec.ts` — verify calibration + timeline render from new mock data

---

## Backend: Gateway Query Layer

### `services/api-gateway/data_queries.py`

Three functions, each taking a SQLAlchemy `Session` and returning a plain dict:

```python
BADGE_CATALOG = {
    'first-prediction': {
        'name': 'First Prediction',
        'description': 'Made your first prediction.',
        'icon': '🎯',
    },
    'above-baseline': {
        'name': 'Above Baseline',
        'description': 'Mean Brier score below 0.25.',
        'icon': '📈',
    },
    # extend as badge_ids are introduced
}

def get_dashboard_data(session: Session, user_id: UUID) -> dict:
    """
    Returns user profile, score summary, earned badges, and up to 5 recent predictions.
    If user has no user_scores row, returns zeroed score fields and empty arrays.
    """

def get_predictions(
    session: Session,
    user_id: UUID,
    source: str | None,
    status: str | None,   # 'resolved' | 'pending'
    sort: str | None,     # 'date' | 'brier_score'
) -> dict:
    """
    Returns up to 50 predictions matching filters, plus a total count of all matching rows.
    sort='date' → created_at desc; sort='brier_score' → brier_score asc (lower is better).
    """

def get_stats_data(session: Session, user_id: UUID) -> dict:
    """
    Returns score summary, calibration buckets (10 bins computed on-the-fly),
    and monthly Brier score timeline (computed on-the-fly from resolved predictions).
    """
```

Calibration buckets: divide [0, 1] into 10 equal bins, group resolved predictions by their `probability` bin, and for each bin compute `{ bin: midpoint, predicted: bin_midpoint, actual: mean(outcome), count: n }`.

Brier timeline: group resolved predictions by `floor(resolved_at, 'month')`, compute `mean(brier_score)` per month, return `{ date: 'YYYY-MM', score: float }` ordered ascending.

---

## Backend: Gateway Route Handlers

### `services/api-gateway/router.py`

Replace the three stub handlers. All require a valid JWT via the existing auth dependency. All enforce `user_id == str(current_user.id)` — return 403 otherwise.

```python
@router.get("/users/{user_id}/dashboard")
async def get_dashboard(user_id: str, current_user=Depends(get_current_user), session=Depends(get_session)):
    if user_id != str(current_user.id):
        raise HTTPException(status_code=403)
    return get_dashboard_data(session, current_user.id)

@router.get("/users/{user_id}/predictions")
async def list_predictions(
    user_id: str,
    source: str | None = None,
    status: str | None = None,
    sort: str | None = None,
    current_user=Depends(get_current_user),
    session=Depends(get_session),
):
    if user_id != str(current_user.id):
        raise HTTPException(status_code=403)
    return get_predictions(session, current_user.id, source, status, sort)

@router.get("/users/{user_id}/stats")
async def get_stats(user_id: str, current_user=Depends(get_current_user), session=Depends(get_session)):
    if user_id != str(current_user.id):
        raise HTTPException(status_code=403)
    return get_stats_data(session, current_user.id)
```

The gateway needs two FastAPI dependencies:
- `get_current_user` — import from `auth_service.api` if it is exported there; otherwise copy the JWT-decode logic into a new `gateway/auth.py` following the same pattern.
- `get_session` — add a `services/api-gateway/database.py` that creates a SQLAlchemy `SessionLocal` bound to `DATABASE_URL` (same env var the auth-service uses) and yields a session. Do not reuse the auth-service's internal session factory directly; the gateway should own its own session lifecycle.

---

## Frontend: API Client

### `apps/user-dashboard/src/lib/api.js`

Add three functions following the existing pattern:

```javascript
export async function getDashboard(userId, token) {
  const res = await fetch(`${BASE}/users/${userId}/dashboard`, {
    headers: { Authorization: `Bearer ${token}` },
  });
  if (!res.ok) throw new Error(`API ${res.status}`);
  return res.json();
}

export async function getPredictions(userId, token, { source = '', status = '', sort = 'date' } = {}) {
  const params = new URLSearchParams({ source, status, sort });
  const res = await fetch(`${BASE}/users/${userId}/predictions?${params}`, {
    headers: { Authorization: `Bearer ${token}` },
  });
  if (!res.ok) throw new Error(`API ${res.status}`);
  return res.json();
}

export async function getUserStats(userId, token) {
  const res = await fetch(`${BASE}/users/${userId}/stats`, {
    headers: { Authorization: `Bearer ${token}` },
  });
  if (!res.ok) throw new Error(`API ${res.status}`);
  return res.json();
}
```

---

## Frontend: Route Loaders

### `apps/user-dashboard/src/routes/dashboard/+page.server.js`

```javascript
import { getDashboard } from '$lib/api.js';

export async function load({ parent }) {
  const { user, token } = await parent();
  const data = await getDashboard(user.id, token);
  return {
    user: data.user,
    score: data.score,
    badges: data.badges,
    recentPredictions: data.recent_predictions,
  };
}
```

### `apps/user-dashboard/src/routes/predictions/+page.server.js`

```javascript
import { getPredictions } from '$lib/api.js';

export async function load({ parent, url }) {
  const { user, token } = await parent();
  const source = url.searchParams.get('source') ?? '';
  const status = url.searchParams.get('status') ?? '';
  const sort   = url.searchParams.get('sort')   ?? 'date';
  const data = await getPredictions(user.id, token, { source, status, sort });
  return {
    predictions: data.predictions,
    total: data.total,
    filters: { source, status, sort },
  };
}
```

### `apps/user-dashboard/src/routes/stats/+page.server.js`

```javascript
import { getUserStats } from '$lib/api.js';

export async function load({ parent }) {
  const { user, token } = await parent();
  const data = await getUserStats(user.id, token);
  return {
    score: data.score,
    calibration: data.calibration,
    brierTimeline: data.brier_timeline,
  };
}
```

**Error handling:** if any API call throws (non-OK response), the loader propagates the error and SvelteKit renders the nearest `+error.svelte`. Non-2xx from the gateway on a data endpoint does not clear the auth cookie (only a 401 on `/auth/me` does that).

---

## Mock Server Updates

### `tests/ui-shared/mock-api-server.mjs`

Add three route patterns (`:userId` matches any segment):

```javascript
'/users/:userId/dashboard'   → responses/dashboard.json
'/users/:userId/predictions' → responses/predictions.json
'/users/:userId/stats'       → responses/stats.json
```

### Response files

**`responses/dashboard.json`** — shape:
```json
{
  "user": { "id": "dev", "username": "dev", "display_name": "Dev User", "email": "dev@localhost", "bio": null, "avatar_url": null, "social_links": {} },
  "score": { "total_predictions": 10, "resolved_predictions": 6, "mean_brier_score": 0.18, "calibration_score": 0.82, "accuracy": 0.67, "last_scored_at": "2026-04-01T00:00:00Z" },
  "badges": [
    { "id": "first-prediction", "name": "First Prediction", "description": "Made your first prediction.", "icon": "🎯", "earned_at": "2025-10-15T00:00:00Z" }
  ],
  "recent_predictions": [
    { "id": "p1", "market_id": "m1", "source": "kalshi", "probability": 0.7, "outcome": 1, "brier_score": 0.09, "created_at": "2026-03-01T00:00:00Z", "resolved_at": "2026-03-15T00:00:00Z" }
  ]
}
```

**`responses/predictions.json`** — shape:
```json
{
  "predictions": [
    { "id": "p1", "market_id": "m1", "source": "kalshi", "probability": 0.7, "outcome": 1, "brier_score": 0.09, "created_at": "2026-03-01T00:00:00Z", "resolved_at": "2026-03-15T00:00:00Z", "rationale": null },
    { "id": "p2", "market_id": "m2", "source": "manifold", "probability": 0.4, "outcome": null, "brier_score": null, "created_at": "2026-03-20T00:00:00Z", "resolved_at": null, "rationale": null }
  ],
  "total": 10
}
```

**`responses/stats.json`** — shape:
```json
{
  "score": { "total_predictions": 10, "resolved_predictions": 6, "mean_brier_score": 0.18, "calibration_score": 0.82, "accuracy": 0.67, "last_scored_at": "2026-04-01T00:00:00Z" },
  "calibration": [
    { "bin": 0.05, "predicted": 0.05, "actual": 0.0,  "count": 1 },
    { "bin": 0.15, "predicted": 0.15, "actual": 0.0,  "count": 0 },
    { "bin": 0.25, "predicted": 0.25, "actual": 0.25, "count": 2 },
    { "bin": 0.35, "predicted": 0.35, "actual": 0.0,  "count": 0 },
    { "bin": 0.45, "predicted": 0.45, "actual": 0.5,  "count": 2 },
    { "bin": 0.55, "predicted": 0.55, "actual": 0.5,  "count": 0 },
    { "bin": 0.65, "predicted": 0.65, "actual": 0.67, "count": 3 },
    { "bin": 0.75, "predicted": 0.75, "actual": 0.75, "count": 4 },
    { "bin": 0.85, "predicted": 0.85, "actual": 1.0,  "count": 2 },
    { "bin": 0.95, "predicted": 0.95, "actual": 1.0,  "count": 2 }
  ],
  "brier_timeline": [
    { "date": "2025-10", "score": 0.22 },
    { "date": "2025-11", "score": 0.20 },
    { "date": "2025-12", "score": 0.19 },
    { "date": "2026-01", "score": 0.18 },
    { "date": "2026-02", "score": 0.17 },
    { "date": "2026-03", "score": 0.18 }
  ]
}
```

---

## Contract Tests

No new spec files needed. Update existing specs to align with the new mock response shapes:

- **`tests/contract/dashboard.spec.ts`** — add assertion: `await expect(page.getByText(/mock data mode/i)).toBeVisible()` (confirms devBypass session is active in contract mode). Update stat value assertions to match `dashboard.json`.
- **`tests/contract/predictions.spec.ts`** — verify 2 prediction rows are visible (matching the 2 entries in `predictions.json`). Verify the total count label shows 10. Verify that interacting with the source filter dropdown updates the page URL to include `?source=<value>` (the mock server returns the same 2 rows regardless of filter params, so contract tests assert the UI mechanism — URL state — not filtered row counts, which require a real backend).
- **`tests/contract/stats.spec.ts`** — verify calibration chart and timeline render; assert at least one data point from `stats.json` is visible in the page.

---

## Error Handling Summary

| Condition | Gateway response | Frontend behaviour |
|-----------|-----------------|-------------------|
| `user_id != current_user.id` | 403 | Loader throws → `+error.svelte` |
| User has no `user_scores` row | 200 with zeroed fields + empty arrays | Renders empty state ("No predictions yet") |
| Unexpected DB error | 500 | Loader throws → `+error.svelte` |
| 401 on `/auth/me` (layout) | 401 | Cookie cleared, redirect `/login` |
