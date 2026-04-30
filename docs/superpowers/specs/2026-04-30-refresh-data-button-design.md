# Refresh Data Button — Design Spec

**Date:** 2026-04-30
**Status:** Approved

## Goal

Add a "Refresh data" button to the user dashboard header that triggers an on-demand sync of the user's prediction history across all linked platforms, with a live working indicator and per-platform error surfacing on completion.

---

## Decisions

| Question | Decision |
|---|---|
| Sync mode | Fire-and-forget: API returns 202 immediately, sync runs in background |
| Completion detection | Poll `GET /users/{user_id}/dashboard` every 3s; when `last_synced_at` advances, reload |
| Partial failure UX | Show amber warning banner naming the platform(s) that errored |
| Button placement | Dashboard page-header, top-right, alongside "Last scored" timestamp |
| Sync trigger architecture | FastAPI `BackgroundTasks` in api-gateway; `sync_one_user` imported from scheduler |

---

## Data Model

**Migration:** `0007_linked_account_sync_status`

Two nullable columns added to `linked_accounts`:

| Column | Type | Behaviour |
|---|---|---|
| `last_synced_at` | `TIMESTAMP WITH TIME ZONE` | Set to `NOW()` when a platform sync attempt finishes (success or failure) |
| `last_sync_error` | `TEXT` | Error message if the sync failed; `NULL` on success |

No other schema changes.

---

## Backend

### New endpoint: `POST /users/{user_id}/sync`

**File:** `services/api-gateway/api_gateway/router.py`

- Auth: `get_current_user` dependency + ownership check (`user_id != current_user.id` → 403), same as all other routes.
- **Server-side rate limit:** if `MAX(last_synced_at)` across the user's linked accounts is within the last 60 seconds, return `429 {"detail": "Sync triggered too recently, please wait"}`.
- Returns `202 {"status": "syncing"}` immediately.
- Registers a FastAPI `BackgroundTask` that:
  1. Opens its own `AsyncSession` (outside the request lifecycle, using the session factory).
  2. Calls `sync_one_user(db, user_id)` imported from `scheduler.sync`.
  3. Commits and closes the session.

### `sync_one_user` updates

**File:** `services/scheduler/scheduler/sync.py`

Two additions to the per-platform dispatch loop in `sync_one_user`:

1. **On success:** after `count = await _sync_<platform>(db, account)`, set:
   ```python
   account.last_synced_at = datetime.now(timezone.utc)
   account.last_sync_error = None
   ```
2. **On failure:** in the existing `except` block, also set:
   ```python
   account.last_sync_error = str(exc)
   account.last_synced_at = datetime.now(timezone.utc)
   ```

This ensures `last_synced_at` advances on every sync attempt so the frontend can detect completion even when a platform errors.

### Dashboard query updates

**File:** `services/api-gateway/api_gateway/data_queries.py`

`get_dashboard` adds two new fields to its response:

- `last_synced_at: datetime | None` — `MAX(last_synced_at)` across the user's linked accounts.
- `sync_status: list[{platform, last_synced_at, error}]` — one entry per linked account, for partial-failure surfacing.

### API client

**File:** `apps/user-dashboard/src/lib/api.js`

New function:
```js
export async function triggerSync(userId, token) {
  return apiFetch(`/users/${userId}/sync`, { method: 'POST', token });
}
```

---

## Frontend

### Button states

Three visual states for the Refresh button in the dashboard header:

| State | Appearance |
|---|---|
| Idle | "Refresh data" button, enabled |
| Syncing | Spinner + "Syncing…", button disabled |
| Post-sync | Returns to idle; amber warning banner shown if any platform errored |

### Placement

Right side of `.page-header` flex container, below the "Last scored" timestamp (same column, stacked).

### Polling logic (`+page.svelte`)

1. On click: call `triggerSync()`. Record `baselineSyncedAt` from currently loaded `data.last_synced_at`. Enter syncing state. Disable button for 30 seconds (client-side rate limit).
2. Start polling: every 3 seconds, `fetch` the dashboard endpoint directly from the browser (`PUBLIC_API_BASE_URL`).
3. **Completion:** when polled `last_synced_at > baselineSyncedAt`, call SvelteKit `invalidateAll()` to reload all load functions on the current page. Stop polling. Dismiss spinner.
4. **Partial failure:** if any entry in `sync_status` has a non-null `error`, show dismissable amber banner: "Sync complete — {platform} returned an error."
5. **Timeout:** if 90 seconds elapse without completion, dismiss spinner regardless. User sees updated data on next navigation.

### Files changed

| File | Change |
|---|---|
| `apps/user-dashboard/src/routes/dashboard/+page.svelte` | Add Refresh button, spinner state, polling logic, error banner |
| `apps/user-dashboard/src/lib/api.js` | Add `triggerSync` |
| `services/api-gateway/api_gateway/router.py` | Add `POST /users/{user_id}/sync` |
| `services/api-gateway/api_gateway/data_queries.py` | Add `last_synced_at`, `sync_status` to dashboard response |
| `services/scheduler/scheduler/sync.py` | Write `last_synced_at` / `last_sync_error` on each platform attempt |
| `services/data-layer/alembic/versions/0007_linked_account_sync_status.py` | Create migration |
| `services/data-layer/data/models/linked_account.py` | Add two columns to `LinkedAccount` model |

---

## Rate Limiting Summary

| Layer | Rule |
|---|---|
| Client-side | Button disabled for 30s after click |
| Server-side | 429 if any `linked_account.last_synced_at` is within the last 60s |

---

## Out of Scope

- Refresh button on predictions or stats pages (dashboard only for now)
- Push notifications or WebSocket-based completion signalling
- Per-platform retry logic (existing scheduled sync handles recovery)
