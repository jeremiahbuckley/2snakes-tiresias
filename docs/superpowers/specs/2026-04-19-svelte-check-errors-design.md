# Fix svelte-check Errors — Design Spec
**Date:** 2026-04-19
**Scope:** 22 type errors across 4 files in apps/user-dashboard/src. No behavioral changes — type annotations only.

---

## Error Categories

### A: Date subtraction (6 errors — 2 files)

TypeScript rejects `new Date(x) - new Date(y)` because `Date` objects don't support arithmetic operators.

**Files:**
- `src/routes/dashboard/+page.server.js:13`
- `src/routes/predictions/+page.server.js:25, 27`

**Fix:** Replace `new Date(x) - new Date(y)` with `new Date(x).getTime() - new Date(y).getTime()` at each occurrence.

---

### B: Local `api()` options parameter type (15 errors — 1 file)

`src/routes/settings/+page.server.js` defines:
```js
async function api(fetch, path, { token, method = 'GET', body } = {}) {
```
TypeScript infers the parameter type from the `{}` default as `{ method?: string }` — missing `token` and `body`. All 15 errors are callers passing `{ token, ... }` to this function.

**Fix:** Add a JSDoc `@param` annotation to `api()`:
```js
/**
 * @param {typeof fetch} fetchFn
 * @param {string} path
 * @param {{ token?: string, method?: string, body?: unknown }} [options]
 */
async function api(fetchFn, path, { token, method = 'GET', body } = {}) {
```

Note: first parameter renamed `fetchFn` to avoid shadowing the global `fetch` — no behavioral change, just avoids an implicit any.

---

### C: `fetchOptions.headers` (1 error — 1 file)

`src/lib/api.js` defines:
```js
async function apiFetch(path, options = {}) {
  const { token, ...fetchOptions } = options;
  ...
  ...(fetchOptions.headers ?? {}),
```
TypeScript infers `options` as `{}` from the default, so `fetchOptions` is also typed as `{}` — no `headers` property.

**Fix:** Add a JSDoc `@param` annotation to `apiFetch()`:
```js
/**
 * @param {string} path
 * @param {{ token?: string, method?: string, body?: string, headers?: Record<string, string> }} [options]
 */
async function apiFetch(path, options = {}) {
```

---

## Success Criteria

`cd apps/user-dashboard && npm run check` exits 0 with 0 errors (2 warnings about unassociated labels are pre-existing Svelte a11y warnings, not errors — acceptable to leave).

## Out of Scope

- The 2 a11y warnings (`label` not associated with a control) — warnings, not errors; fixing them requires HTML changes to the filter UI, separate task
- Any logic changes
- Any API or data model changes
