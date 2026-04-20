# Phase 2 Playwright Tests — Design Spec
**Date:** 2026-04-19
**Scope:** First real test files for `apps/user-dashboard` — 4 contract specs (all protected routes) + 1 smoke spec (login flow). No behavioral changes to the SvelteKit app itself.

---

## Architecture

All server-side API calls in the SvelteKit app (`+layout.server.js`, `settings/+page.server.js`) read the API base URL from `process.env.API_BASE_URL`. Contract tests exploit this: the SvelteKit dev server is started with `API_BASE_URL=http://localhost:8001`, pointing at a lightweight mock HTTP server instead of the real API gateway. No real backend needed, CI-safe.

Two Playwright config files replace the existing combined config:

| Config | Suite | webServer |
|---|---|---|
| `playwright.config.ts` | smoke | none (user starts real stack manually) |
| `playwright.contract.config.ts` | contract | mock API server on 8001 + SvelteKit dev server with `API_BASE_URL` override |

The contract fixture no longer calls `assertTestUserConfigured()` — the mock server accepts any credentials. Hardcoded test credentials (`test@contract.local` / `contract-password`) are used in the contract fixture so CI never needs real user env vars.

---

## Mock API Server

**File:** `tests/ui-shared/mock-api-server.mjs`
**Port:** 8001 (avoids conflict with real API on 8000)
**Runtime:** Node.js built-in `http` module — zero added dependencies

Endpoints handled:

| Method | Path | Used by |
|---|---|---|
| `POST` | `/auth/login` | Login form action |
| `GET` | `/auth/me` | `+layout.server.js` — auth validation on every protected route load |
| `GET` | `/auth/me/linked-accounts` | `settings/+page.server.js` load |
| `GET` | `/auth/me/share-tokens` | `settings/+page.server.js` load |
| `GET` | `/auth/me/notifications` | `settings/+page.server.js` load |

Any unregistered route returns `500` with `{ detail: "No mock for METHOD /path" }` — consistent with the client-side `handlers.ts` pattern.

Response JSON files live in `tests/ui-shared/api-mocks/responses/` and match the shapes of `src/lib/mock.js`:

| File | Content |
|---|---|
| `auth-login.json` | `{ "access_token": "contract-test-token" }` |
| `auth-me.json` | Mock user object (matches `mockUser` shape) |
| `linked-accounts.json` | Mock linked accounts (kalshi+polymarket enabled, manifold disabled, metaculus not linked) |
| `share-tokens.json` | One active share token |
| `notifications.json` | `{ email_on_resolution: true, email_on_badge: true, email_on_rank_change: false }` |

---

## File Map

| Action | Path |
|---|---|
| Create | `tests/ui-shared/mock-api-server.mjs` |
| Create | `tests/ui-shared/api-mocks/responses/auth-login.json` |
| Create | `tests/ui-shared/api-mocks/responses/auth-me.json` |
| Create | `tests/ui-shared/api-mocks/responses/linked-accounts.json` |
| Create | `tests/ui-shared/api-mocks/responses/share-tokens.json` |
| Create | `tests/ui-shared/api-mocks/responses/notifications.json` |
| Modify | `tests/ui-shared/fixtures.ts` — contract fixture: remove `assertTestUserConfigured()`, use hardcoded credentials |
| Modify | `apps/user-dashboard/playwright.config.ts` — slim to smoke-only, no webServer |
| Create | `apps/user-dashboard/playwright.contract.config.ts` — contract-only, two webServer entries |
| Modify | `apps/user-dashboard/package.json` — update test scripts to point at correct config files |
| Create | `apps/user-dashboard/tests/smoke/login.spec.ts` |
| Create | `apps/user-dashboard/tests/contract/dashboard.spec.ts` |
| Create | `apps/user-dashboard/tests/contract/predictions.spec.ts` |
| Create | `apps/user-dashboard/tests/contract/settings.spec.ts` |
| Create | `apps/user-dashboard/tests/contract/stats.spec.ts` |

---

## Test Coverage

### Smoke: `tests/smoke/login.spec.ts`

Uses the `test` fixture's `guestPage` (unauthenticated page). Requires real stack + `TEST_USER` credentials in `.env.test`.

- **Login flow:** Navigate to `/login` → fill email + password → click Log in → assert redirect to `/dashboard`
- **Auth redirect:** Navigate to any protected route while unauthenticated → assert redirect to `/login`

### Contract: `tests/contract/dashboard.spec.ts`

Uses `contractTest.authedPage`. Mock server provides auth; route returns mock.js data directly.

- **Score stats:** Total predictions count and resolved count from mock data are visible on the page
- **Recent predictions list:** Exactly 5 items rendered
- **Badges:** At least one badge visible on the page

### Contract: `tests/contract/predictions.spec.ts`

Uses `contractTest.authedPage`. Filter interactions trigger server-side re-loads with query params.

- **Initial render:** Prediction rows visible (all 10 from mock data, no filter applied)
- **Source filter:** Select "Kalshi" from source dropdown → page reloads → only Kalshi predictions shown
- **Status filter:** Select "Resolved" from status dropdown → only resolved predictions shown
- **Sort interaction:** Change sort from default to "Date (oldest first)" → row order changes

### Contract: `tests/contract/settings.spec.ts`

Uses `contractTest.authedPage`. Mock server provides linked-accounts, share-tokens, notifications responses.

- **Linked accounts render:** Kalshi shown as linked; Metaculus shown as not linked (from mock response)
- **Notification prefs render:** Email-on-resolution and email-on-badge checkboxes visible and checked; email-on-rank-change unchecked
- **Profile edit interaction:** Click Edit (or equivalent) in the profile section → form fields become editable/focused

### Contract: `tests/contract/stats.spec.ts`

Uses `contractTest.authedPage`. Route returns mock.js data directly.

- **Brier score:** Mean Brier score value visible on the page
- **Calibration section:** Section heading or chart container visible
- **Timeline section:** Brier timeline section heading or chart container visible

---

## Fixture Change

`tests/ui-shared/fixtures.ts` — `contractTest.authedPage` changes:

**Before:**
```typescript
authedPage: async ({ page }, use) => {
  assertTestUserConfigured();
  await registerApiMocks(page);
  await login(page, TEST_USER.email, TEST_USER.password);
  await use(page);
}
```

**After:**
```typescript
authedPage: async ({ page }, use) => {
  // Mock server accepts any credentials — no real user needed
  await login(page, 'test@contract.local', 'contract-password');
  await use(page);
}
```

`registerApiMocks(page)` is removed from the contract fixture (all API calls are server-side; the mock server handles them). It remains available for future use when client-side API calls are added.

---

## Success Criteria

- `npm run test:contract` exits 0 with all contract tests passing, no real backend running
- `npm run test:smoke` (with real stack running and `.env.test` configured) exits 0
- `npm run check` continues to exit 0 (no type regressions)
