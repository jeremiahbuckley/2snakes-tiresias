# Tag-Awareness UI

**Date:** 2026-04-27
**Status:** Approved
**Scope:** `services/api-gateway`, `apps/user-dashboard`, `apps/public-profile`, `services/auth-service`

## Problem

Tags are stored on markets and flow through to the predictions API response, but the UI has no way to filter or aggregate by tag. Users cannot see how they perform on a specific topic (e.g. politics, crypto) and cannot isolate predictions by subject area on any page.

## Goal

Add an optional tag filter to all four user-facing surfaces — predictions list, stats page, dashboard, and public profile. When a tag is selected, all data on that page recomputes to show only predictions from markets tagged with that value.

## Non-Goals

- Pre-computing per-domain scores in `UserScore` (deferred; add if on-demand queries prove too slow)
- Global/persistent tag filter that follows the user across pages (each page manages its own filter independently)
- Multi-tag filtering (single tag at a time for V1)

---

## Architecture

An optional `tag` query parameter is added to all four data endpoints. When absent, all existing behavior is unchanged. When present, every DB query filters to predictions whose associated market's `tags` array contains that value (`Market.tags.contains([tag])`).

**Tag discovery:** Each page response gains an `available_tags: list[str]` field, computed by a shared `_user_tags(user_id, db)` helper that queries distinct tags from markets linked to the user's predictions. This avoids a separate network round trip for dropdown population.

**Stats recomputation:** `UserScore` is a pre-aggregated denormalized cache and cannot be tag-filtered post-hoc. When `tag` is set, `get_stats_data` bypasses `UserScore` and recomputes mean Brier, calibration bins, and monthly timeline directly from filtered `Prediction` rows — the same math, applied to a subset.

---

## Backend Changes

### `api_gateway/data_queries.py`

**New helper:**
```python
async def _user_tags(user_id: UUID, db: AsyncSession) -> list[str]:
    """Return sorted list of all distinct tags from markets the user has predictions for."""
```
One query: join `Prediction → Market`, unnest `Market.tags`, return deduplicated sorted list.

**`get_predictions(user_id, tag=None, ...)`**
- When `tag` is set: join to `Market`, add `Market.tags.contains([tag])` filter
- Response gains `available_tags: list[str]`

**`get_stats_data(user_id, tag=None)`**
- When `tag` is set: fetch filtered `Prediction` rows directly; recompute mean Brier, BSS, calibration curve, and monthly Brier timeline from them
- When `tag` is absent: keep existing `UserScore` read path
- Response gains `available_tags: list[str]`
- Domain breakdown table is omitted from the response when `tag` is set (redundant)

**`get_dashboard_data(user_id, tag=None)`**
- When `tag` is set: bypass `UserScore` and recompute summary stats and per-source breakdown from filtered `Prediction` rows directly; filter recent activity to the same tag
- Response gains `available_tags: list[str]`

### `api_gateway/router.py`

Each of the four route handlers gains:
```python
tag: Optional[str] = Query(default=None)
```
Passed through to the corresponding data function.

### `auth_service/api.py` — share token endpoint

`GET /auth/share/{token_slug}` gains `tag: Optional[str] = Query(default=None)`. Delegates to the same filtered data functions as the authenticated endpoints.

---

## Frontend Changes

### Shared component: `TagFilter`

A reusable Svelte component used on all four pages:
- Props: `availableTags: string[]`, `selectedTag: string | null`
- Renders a `<select>` with an "All tags" option followed by sorted tag values
- On change: updates the URL search param `tag=` (empty string removes it)
- Visually indicates the active tag (same style as the existing Platform filter)

### Predictions page (`/predictions`)

**Filter bar** — `TagFilter` added alongside Platform and Status filters. Reads from `?tag=` URL param; resets to page 1 on change. Populated from `data.available_tags` (top-level field on the predictions response).

**Tag pills on prediction rows** — the Category column (currently `pred.tags[0]`) becomes a set of pill buttons, one per tag on that prediction. Clicking a pill sets `?tag=<value>` in the URL, which updates both the active filter and the dropdown. The pill matching the active tag is visually highlighted.

**`+page.server.js`** — reads `tag` from URL params, passes to `getPredictions()`. Same pattern as existing `source` and `status` params.

### Stats page (`/stats`)

`TagFilter` added at the top of the page. `+page.server.js` reads `?tag=` and passes to the stats endpoint. All displayed values recompute from the filtered response. A subtitle "Showing: {tag}" appears below the page heading when a tag is active. Domain breakdown table is hidden when a tag filter is active.

### Dashboard (`/dashboard`)

`TagFilter` added at the top of the page. Summary cards, platform breakdown, and recent activity all recompute from tag-filtered data. Same "Showing: {tag}" subtitle.

### Public profile (`apps/public-profile`)

`TagFilter` rendered only when the share token has `show_predictions: true`. Reads `?tag=` from URL; passes to the share endpoint. Same subtitle indicator.

---

## Data Flow (tag-filtered request)

```
User selects "politics" tag
  → URL updates: ?tag=politics
  → SvelteKit invalidates page data
  → +page.server.js reads tag param
  → Calls API: GET /users/{id}/stats?tag=politics
  → api_gateway: filters Prediction JOIN Market WHERE 'politics' = ANY(tags)
  → Recomputes calibration, timeline, mean Brier from filtered rows
  → Returns { score, calibration, brier_timeline, available_tags }
  → UI renders with "Showing: politics" indicator
```

---

## Error Handling

- Unknown or misspelled tag in URL param: API returns empty results (no predictions match), UI shows "No predictions for this tag" empty state. No 400 error — unrecognised tags are not a caller error.
- Tag param present but `available_tags` does not include it (e.g. stale URL): same empty-state behavior.

---

## Testing

### Backend (pytest)

- `get_predictions` with `tag=` returns only predictions from markets containing that tag
- `get_predictions` without `tag=` is unchanged
- `get_stats_data` with `tag=` bypasses `UserScore` and computes from filtered predictions
- `get_stats_data` without `tag=` uses `UserScore` (existing behavior)
- `get_dashboard_data` with `tag=` recomputes summary stats from filtered set
- `_user_tags` returns deduplicated sorted tags for a user
- Unknown tag returns empty predictions and zero/null stats (not an error)

### Frontend (contract tests)

- Tag dropdown renders with `available_tags` from mock response
- Selecting a tag updates the URL param
- Clicking a tag pill on a prediction row updates the URL param and dropdown
- "Showing: {tag}" subtitle appears when tag is active
- Domain breakdown table hidden on stats page when tag active
- Public profile tag filter only renders when `show_predictions: true`

---

## Out of Scope

- Pre-computing per-domain scores in `UserScore` — deferred
- Multi-tag filtering
- Tag management (renaming, merging, hiding tags)
- Sorting/ranking by tag performance
