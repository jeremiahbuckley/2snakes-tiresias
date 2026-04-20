# Fix svelte-check Type Errors Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Eliminate all 22 type errors reported by `svelte-check` in `apps/user-dashboard` via minimal JSDoc annotations and `.getTime()` fixes — no behavioral changes.

**Architecture:** Three error categories across four files. All fixes are additive (annotations only) or one-line substitutions. Each task targets one file, verified by running `svelte-check` scoped to that file's errors, then committed.

**Tech Stack:** SvelteKit 2, Svelte 4, TypeScript (via svelte-check on JS files), JSDoc

---

## File Map

| Action | Path | Errors fixed |
|---|---|---|
| Modify | `apps/user-dashboard/src/routes/dashboard/+page.server.js` | 2 — Date subtraction |
| Modify | `apps/user-dashboard/src/routes/predictions/+page.server.js` | 4 — Date subtraction |
| Modify | `apps/user-dashboard/src/routes/settings/+page.server.js` | 15 — api() options type |
| Modify | `apps/user-dashboard/src/lib/api.js` | 1 — apiFetch options type |

---

## Task 1: Fix Date subtraction in dashboard/+page.server.js

**Files:**
- Modify: `apps/user-dashboard/src/routes/dashboard/+page.server.js:13`

`new Date(x) - new Date(y)` is invalid TypeScript — `Date` objects don't support arithmetic. Fix with `.getTime()`.

- [ ] **Step 1: Confirm the error exists**

```bash
cd apps/user-dashboard && npm run check 2>&1 | grep "dashboard"
```

Expected: two lines mentioning `+page.server.js:13` about arithmetic types.

- [ ] **Step 2: Apply the fix**

In `src/routes/dashboard/+page.server.js`, change line 13 from:
```js
  .sort((a, b) => new Date(b.created_at) - new Date(a.created_at))
```
to:
```js
  .sort((a, b) => new Date(b.created_at).getTime() - new Date(a.created_at).getTime())
```

The full function after the fix:
```js
/** @type {import('./$types').PageServerLoad} */
export async function load({ cookies }) {
  const token = cookies.get('tiresias_token');

  // TODO: replace with real API calls once api-gateway is live:
  //   const user   = await getMe(token);
  //   const dashboard = await getDashboard(user.user_id, token);

  const recentPredictions = mockPredictions
    .slice()
    .sort((a, b) => new Date(b.created_at).getTime() - new Date(a.created_at).getTime())
    .slice(0, 5);

  return {
    user: mockUser,
    score: mockScore,
    badges: mockBadges,
    recentPredictions,
  };
}
```

- [ ] **Step 3: Verify dashboard errors are gone**

```bash
cd apps/user-dashboard && npm run check 2>&1 | grep "dashboard"
```

Expected: no output (no dashboard errors).

- [ ] **Step 4: Commit**

```bash
git add apps/user-dashboard/src/routes/dashboard/+page.server.js
git commit -m "fix: use .getTime() for Date comparison in dashboard sort"
```

---

## Task 2: Fix Date subtraction in predictions/+page.server.js

**Files:**
- Modify: `apps/user-dashboard/src/routes/predictions/+page.server.js:25,27`

Two sort comparisons use `new Date(x) - new Date(y)`. Fix both with `.getTime()`.

- [ ] **Step 1: Confirm the errors exist**

```bash
cd apps/user-dashboard && npm run check 2>&1 | grep "predictions/+page.server"
```

Expected: four lines (two per sort call) about arithmetic types.

- [ ] **Step 2: Apply the fix**

In `src/routes/predictions/+page.server.js`, change lines 25 and 27.

Before (lines 24–28):
```js
  if (sortBy === 'date_desc') {
    predictions.sort((a, b) => new Date(b.created_at) - new Date(a.created_at));
  } else if (sortBy === 'date_asc') {
    predictions.sort((a, b) => new Date(a.created_at) - new Date(b.created_at));
  } else if (sortBy === 'brier_asc') {
```

After:
```js
  if (sortBy === 'date_desc') {
    predictions.sort((a, b) => new Date(b.created_at).getTime() - new Date(a.created_at).getTime());
  } else if (sortBy === 'date_asc') {
    predictions.sort((a, b) => new Date(a.created_at).getTime() - new Date(b.created_at).getTime());
  } else if (sortBy === 'brier_asc') {
```

- [ ] **Step 3: Verify predictions errors are gone**

```bash
cd apps/user-dashboard && npm run check 2>&1 | grep "predictions/+page.server"
```

Expected: no output.

- [ ] **Step 4: Commit**

```bash
git add apps/user-dashboard/src/routes/predictions/+page.server.js
git commit -m "fix: use .getTime() for Date comparison in predictions sort"
```

---

## Task 3: Fix api() options parameter type in settings/+page.server.js

**Files:**
- Modify: `apps/user-dashboard/src/routes/settings/+page.server.js:12–13`

The local `api()` function uses destructuring with a `{}` default, so TypeScript infers the options type as `{ method?: string }` — missing `token` and `body`. Adding a JSDoc `@param` annotation gives TypeScript the correct type.

- [ ] **Step 1: Confirm the errors exist**

```bash
cd apps/user-dashboard && npm run check 2>&1 | grep "settings"
```

Expected: 15 error lines about `token` and `body` not existing on the options type.

- [ ] **Step 2: Apply the fix**

In `src/routes/settings/+page.server.js`, add a JSDoc comment immediately before the `api` function. The existing comment on line 12 becomes part of the JSDoc block.

Before (lines 12–13):
```js
/** Thin fetch wrapper — throws { status, detail } on non-ok responses. */
async function api(fetch, path, { token, method = 'GET', body } = {}) {
```

After:
```js
/**
 * Thin fetch wrapper — throws { status, detail } on non-ok responses.
 * @param {typeof fetch} fetch
 * @param {string} path
 * @param {{ token?: string, method?: string, body?: unknown }} [options]
 */
async function api(fetch, path, { token, method = 'GET', body } = {}) {
```

- [ ] **Step 3: Verify settings errors are gone**

```bash
cd apps/user-dashboard && npm run check 2>&1 | grep "settings"
```

Expected: no output.

- [ ] **Step 4: Commit**

```bash
git add apps/user-dashboard/src/routes/settings/+page.server.js
git commit -m "fix: add JSDoc type annotation to settings api() options parameter"
```

---

## Task 4: Fix apiFetch options parameter type in lib/api.js

**Files:**
- Modify: `apps/user-dashboard/src/lib/api.js:16`

`apiFetch(path, options = {})` defaults to `{}`, so TypeScript infers `options` as `{}` — no `headers` property. Adding a JSDoc `@param` fixes this.

- [ ] **Step 1: Confirm the error exists**

```bash
cd apps/user-dashboard && npm run check 2>&1 | grep "api.js"
```

Expected: one line about `Property 'headers' does not exist on type '{}'`.

- [ ] **Step 2: Apply the fix**

In `src/lib/api.js`, add a JSDoc comment immediately before `apiFetch`.

Before (line 16):
```js
async function apiFetch(path, options = {}) {
```

After:
```js
/**
 * @param {string} path
 * @param {{ token?: string, method?: string, body?: string, headers?: Record<string, string> }} [options]
 */
async function apiFetch(path, options = {}) {
```

- [ ] **Step 3: Verify api.js error is gone**

```bash
cd apps/user-dashboard && npm run check 2>&1 | grep "api.js"
```

Expected: no output.

- [ ] **Step 4: Commit**

```bash
git add apps/user-dashboard/src/lib/api.js
git commit -m "fix: add JSDoc type annotation to apiFetch options parameter"
```

---

## Task 5: Final verification

- [ ] **Step 1: Run full svelte-check**

```bash
cd apps/user-dashboard && npm run check 2>&1
```

Expected: output ends with `svelte-check found 0 errors` (warnings about unassociated `<label>` elements in `predictions/+page.svelte` may still appear — those are pre-existing a11y warnings, not errors, and are out of scope).

- [ ] **Step 2: Confirm exit code is 0**

```bash
cd apps/user-dashboard && npm run check; echo "exit: $?"
```

Expected: `exit: 0`
