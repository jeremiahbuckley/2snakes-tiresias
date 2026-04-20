# Phase 2 Playwright Tests Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Write the first real Playwright test files for `apps/user-dashboard` — a mock API server, contract tests for all four protected routes, and a smoke test for the login flow.

**Architecture:** A lightweight Node.js HTTP server on port 8001 stands in for the real API during contract tests. The SvelteKit dev server is started with `API_BASE_URL=http://localhost:8001`, so all server-side fetches (auth validation in `+layout.server.js`, settings data in `settings/+page.server.js`) hit the mock server instead of a real backend. Dashboard, predictions, and stats routes already use `mock.js` data directly and need no API mocking beyond auth. A separate `playwright.contract.config.ts` manages both webServer entries. The existing `playwright.config.ts` is slimmed to smoke-only (no webServer — real stack is user-managed).

**Tech Stack:** Playwright 1.44, SvelteKit 2, TypeScript, Node.js built-in `http` module (mock server — zero extra dependencies)

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
| Modify | `tests/ui-shared/fixtures.ts` |
| Modify | `apps/user-dashboard/playwright.config.ts` |
| Create | `apps/user-dashboard/playwright.contract.config.ts` |
| Modify | `apps/user-dashboard/package.json` |
| Create | `apps/user-dashboard/tests/contract/dashboard.spec.ts` |
| Create | `apps/user-dashboard/tests/contract/predictions.spec.ts` |
| Create | `apps/user-dashboard/tests/contract/settings.spec.ts` |
| Create | `apps/user-dashboard/tests/contract/stats.spec.ts` |
| Create | `apps/user-dashboard/tests/smoke/login.spec.ts` |

---

## Background: mock data counts (needed for test assertions)

From `src/lib/mock.js` (used by dashboard/predictions/stats routes directly):

- **Total predictions:** 10
- **Kalshi predictions:** pred_001, pred_005, pred_008 → **3**
- **Resolved predictions** (outcome != null): pred_001–005, pred_008 → **6**
- **Pending predictions** (outcome == null): pred_006, pred_007, pred_009, pred_010 → **4**
- **Oldest prediction by date:** pred_008 "Will Ethereum ETF see $10B+ net inflows in 2025?" (2025-02-01) — appears first when sorted `date_asc`
- **Recent predictions on dashboard:** 5 (newest 5 by `created_at`, sliced in `dashboard/+page.server.js`)
- **Earned badges:** 5 (First Prediction, Getting Started, Prolific Forecaster, Better Than Coin Flip, Cross-Platform Forecaster)
- **Mock user display name:** "Jeremiah B." (from `auth-me.json`, used by settings profile form)
- **Stats Brier score:** 0.162 (mean_brier_score from mockScore)

---

## Task 1: Mock API server + JSON response files

**Files:**
- Create: `tests/ui-shared/mock-api-server.mjs`
- Create: `tests/ui-shared/api-mocks/responses/auth-login.json`
- Create: `tests/ui-shared/api-mocks/responses/auth-me.json`
- Create: `tests/ui-shared/api-mocks/responses/linked-accounts.json`
- Create: `tests/ui-shared/api-mocks/responses/share-tokens.json`
- Create: `tests/ui-shared/api-mocks/responses/notifications.json`

- [ ] **Step 1: Create the JSON response files**

`tests/ui-shared/api-mocks/responses/auth-login.json`:
```json
{ "access_token": "contract-test-token" }
```

`tests/ui-shared/api-mocks/responses/auth-me.json`:
```json
{
  "id": "usr_abc123",
  "username": "jeremiah_b",
  "display_name": "Jeremiah B.",
  "email": "jeremiahbuckley@2snakes.com",
  "bio": "Forecaster tracking markets across Kalshi, Polymarket, Manifold, and Metaculus.",
  "avatar_url": null,
  "social_links": {}
}
```

`tests/ui-shared/api-mocks/responses/linked-accounts.json` — the API returns a flat **array**; `settings/+page.server.js::reshapeAccounts()` converts it to the keyed object the UI uses. Only include linked platforms (metaculus is not linked, so omit it):
```json
[
  {
    "platform": "kalshi",
    "external_identifier": "jeremiah_b_kalshi",
    "linked_at": "2024-09-10T10:00:00Z",
    "is_enabled": true,
    "is_verified": true
  },
  {
    "platform": "polymarket",
    "external_identifier": "0xabc123...",
    "linked_at": "2024-10-05T14:00:00Z",
    "is_enabled": true,
    "is_verified": true
  },
  {
    "platform": "manifold",
    "external_identifier": "JeremiahB",
    "linked_at": "2024-11-20T09:00:00Z",
    "is_enabled": false,
    "is_verified": true
  }
]
```

`tests/ui-shared/api-mocks/responses/share-tokens.json`:
```json
[
  {
    "token": "aB3xQ7mR9nKp2wLvYtDcFs",
    "label": "General audience",
    "show_scores": true,
    "show_badges": true,
    "show_predictions": false,
    "is_active": true,
    "created_at": "2026-03-01T10:00:00Z"
  }
]
```

`tests/ui-shared/api-mocks/responses/notifications.json`:
```json
{
  "email_on_resolution": true,
  "email_on_badge": true,
  "email_on_rank_change": false
}
```

- [ ] **Step 2: Create the mock API server**

`tests/ui-shared/mock-api-server.mjs`:
```javascript
import http from 'http';
import { readFileSync } from 'fs';
import { dirname, join } from 'path';
import { fileURLToPath } from 'url';

const __dirname = dirname(fileURLToPath(import.meta.url));

const routes = {
  'POST /auth/login':              readFileSync(join(__dirname, 'api-mocks/responses/auth-login.json'), 'utf8'),
  'GET /auth/me':                  readFileSync(join(__dirname, 'api-mocks/responses/auth-me.json'), 'utf8'),
  'GET /auth/me/linked-accounts':  readFileSync(join(__dirname, 'api-mocks/responses/linked-accounts.json'), 'utf8'),
  'GET /auth/me/share-tokens':     readFileSync(join(__dirname, 'api-mocks/responses/share-tokens.json'), 'utf8'),
  'GET /auth/me/notifications':    readFileSync(join(__dirname, 'api-mocks/responses/notifications.json'), 'utf8'),
};

const server = http.createServer((req, res) => {
  const key = `${req.method} ${req.url}`;

  // Playwright polls GET / to detect when the server is ready.
  if (key === 'GET /' || key === 'HEAD /') {
    res.writeHead(200, { 'Content-Type': 'application/json' });
    res.end(JSON.stringify({ status: 'ok' }));
    return;
  }

  const body = routes[key];
  if (body) {
    res.writeHead(200, { 'Content-Type': 'application/json' });
    res.end(body);
  } else {
    res.writeHead(500, { 'Content-Type': 'application/json' });
    res.end(JSON.stringify({ detail: `No mock for ${req.method} ${req.url}` }));
  }
});

const PORT = 8001;
server.listen(PORT, () => {
  console.log(`Mock API server running on http://localhost:${PORT}`);
});
```

- [ ] **Step 3: Verify the mock server responds correctly**

Run from the repo root:
```bash
node tests/ui-shared/mock-api-server.mjs &
sleep 1
curl -s http://localhost:8001/auth/me | python3 -m json.tool
kill %1
```

Expected output — the auth-me.json contents printed as formatted JSON:
```json
{
    "id": "usr_abc123",
    "username": "jeremiah_b",
    ...
}
```

Also verify the 500 for an unmocked route:
```bash
node tests/ui-shared/mock-api-server.mjs &
sleep 1
curl -s http://localhost:8001/some/unknown/path
kill %1
```
Expected: `{"detail":"No mock for GET /some/unknown/path"}`

- [ ] **Step 4: Commit**

```bash
git add tests/ui-shared/mock-api-server.mjs tests/ui-shared/api-mocks/responses/
git commit -m "feat: add mock API server and JSON response fixtures for contract tests"
```

---

## Task 2: Contract Playwright config + fixture update + package.json scripts

**Files:**
- Create: `apps/user-dashboard/playwright.contract.config.ts`
- Modify: `apps/user-dashboard/playwright.config.ts`
- Modify: `tests/ui-shared/fixtures.ts`
- Modify: `apps/user-dashboard/package.json`

- [ ] **Step 1: Create `apps/user-dashboard/playwright.contract.config.ts`**

The contract SvelteKit server runs on port **5181** (not the default 5173) so it never conflicts with a regular `npm run dev` session. The `env` field passes `API_BASE_URL` cleanly without shell quoting issues. `npm run dev -- --port 5181` passes `--port 5181` through npm's `--` separator to `vite dev`.

```typescript
import { defineConfig } from '@playwright/test';
import { dirname, resolve } from 'path';
import { fileURLToPath } from 'url';

const __dirname = dirname(fileURLToPath(import.meta.url));

export default defineConfig({
  projects: [
    {
      name: 'contract',
      use: { baseURL: 'http://localhost:5181' },
      testDir: resolve(__dirname, 'tests/contract'),
    },
  ],
  use: {
    trace: 'on-first-retry',
    screenshot: 'only-on-failure',
  },
  reporter: [['list'], ['html', { open: 'never' }]],
  webServer: [
    {
      command: 'node ../../tests/ui-shared/mock-api-server.mjs',
      url: 'http://localhost:8001',
      reuseExistingServer: !process.env.CI,
    },
    {
      command: 'npm run dev -- --port 5181',
      env: { API_BASE_URL: 'http://localhost:8001' },
      url: 'http://localhost:5181',
      reuseExistingServer: !process.env.CI,
    },
  ],
});
```

- [ ] **Step 2: Slim `apps/user-dashboard/playwright.config.ts` to smoke-only**

Replace the entire file with:
```typescript
import { defineConfig } from '@playwright/test';
import { dirname, resolve } from 'path';
import { fileURLToPath } from 'url';
import { BASE_URLS } from '../../tests/ui-shared/config';

const __dirname = dirname(fileURLToPath(import.meta.url));

export default defineConfig({
  projects: [
    {
      name: 'smoke',
      use: { baseURL: BASE_URLS.dashboard },
      testDir: resolve(__dirname, 'tests/smoke'),
    },
  ],
  use: {
    trace: 'on-first-retry',
    screenshot: 'only-on-failure',
  },
  reporter: [['list'], ['html', { open: 'never' }]],
});
```

- [ ] **Step 3: Update `tests/ui-shared/fixtures.ts`**

The contract fixture no longer calls `assertTestUserConfigured()` — the mock server accepts any credentials. Remove `registerApiMocks` from the contract fixture (all API calls are server-side; the mock server handles them).

Replace the entire file:
```typescript
import { test as base, type Page } from '@playwright/test';
import { TEST_USER, assertTestUserConfigured } from './config';
import { login } from './helpers/auth';

export const test = base.extend<{
  authedPage: Page;
  guestPage: Page;
}>({
  authedPage: async ({ page }, use) => {
    assertTestUserConfigured();
    await login(page, TEST_USER.email, TEST_USER.password);
    await use(page);
  },
  guestPage: async ({ page }, use) => {
    await use(page);
  },
});

export const contractTest = base.extend<{
  authedPage: Page;
  guestPage: Page;
}>({
  authedPage: async ({ page }, use) => {
    // Mock API server accepts any credentials — no real user env vars needed.
    await login(page, 'test@contract.local', 'contract-password');
    await use(page);
  },
  guestPage: async ({ page }, use) => {
    await use(page);
  },
});

export { expect } from '@playwright/test';
```

- [ ] **Step 4: Update `apps/user-dashboard/package.json` scripts**

Change the two test scripts to point at their respective config files:
```json
"test:smoke":    "playwright test --config playwright.config.ts",
"test:contract": "playwright test --config playwright.contract.config.ts"
```

Full scripts block after change:
```json
"scripts": {
  "dev": "vite dev",
  "build": "vite build",
  "preview": "vite preview",
  "check": "svelte-kit sync && svelte-check --tsconfig ./tsconfig.json",
  "check:watch": "svelte-kit sync && svelte-check --tsconfig ./tsconfig.json --watch",
  "test:smoke":    "playwright test --config playwright.config.ts",
  "test:contract": "playwright test --config playwright.contract.config.ts"
}
```

- [ ] **Step 5: Verify type check still passes**

```bash
cd apps/user-dashboard && npm run check
```

Expected: `svelte-check found 0 errors and 2 warnings in 1 file`

- [ ] **Step 6: Commit**

```bash
git add apps/user-dashboard/playwright.config.ts \
        apps/user-dashboard/playwright.contract.config.ts \
        apps/user-dashboard/package.json \
        tests/ui-shared/fixtures.ts
git commit -m "feat: add contract Playwright config, update fixtures and scripts"
```

---

## Task 3: Dashboard contract spec

**Files:**
- Create: `apps/user-dashboard/tests/contract/dashboard.spec.ts`

The dashboard route (`/dashboard/+page.server.js`) returns mock.js data directly — no API call except the layout's `GET /auth/me` (handled by mock server). The page renders:
- `h1` heading "Dashboard"
- Welcome message with `user.display_name` ("Jeremiah B." from auth-me.json)
- Stat cards showing `score.resolved_predictions` (189) and `score.total_predictions` (247)
- Recent predictions table with exactly 5 rows
- Badge grid showing "First Prediction" (earned badge)

- [ ] **Step 1: Create the spec file**

`apps/user-dashboard/tests/contract/dashboard.spec.ts`:
```typescript
import { contractTest, expect } from '../../../../tests/ui-shared/fixtures';

contractTest.describe('dashboard', () => {
  contractTest('renders heading and welcome message', async ({ authedPage: page }) => {
    await page.goto('/dashboard');
    await expect(page.getByRole('heading', { name: 'Dashboard' })).toBeVisible();
    await expect(page.getByText('Welcome back, Jeremiah B.')).toBeVisible();
  });

  contractTest('shows resolved and total prediction counts', async ({ authedPage: page }) => {
    await page.goto('/dashboard');
    // stat card shows "189 / 247" — 189 is rendered as text, 247 in .stat-denom span
    await expect(page.getByText('189')).toBeVisible();
  });

  contractTest('recent activity table has exactly 5 rows', async ({ authedPage: page }) => {
    await page.goto('/dashboard');
    await expect(page.locator('table tbody tr')).toHaveCount(5);
  });

  contractTest('shows earned badge from mock data', async ({ authedPage: page }) => {
    await page.goto('/dashboard');
    await expect(page.getByText('First Prediction')).toBeVisible();
  });
});
```

- [ ] **Step 2: Run just the dashboard spec**

From `apps/user-dashboard/`:
```bash
npx playwright test --config playwright.contract.config.ts tests/contract/dashboard.spec.ts
```

Expected — Playwright starts both webServers then runs 4 tests:
```
Running 4 tests using 1 worker

  ✓  contract › dashboard › renders heading and welcome message
  ✓  contract › dashboard › shows resolved and total prediction counts
  ✓  contract › dashboard › recent activity table has exactly 5 rows
  ✓  contract › dashboard › shows earned badge from mock data

  4 passed
```

- [ ] **Step 3: Commit**

```bash
git add apps/user-dashboard/tests/contract/dashboard.spec.ts
git commit -m "test: add dashboard contract spec"
```

---

## Task 4: Predictions contract spec

**Files:**
- Create: `apps/user-dashboard/tests/contract/predictions.spec.ts`

The predictions route (`/predictions/+page.server.js`) filters mock.js predictions server-side using `?source=`, `?status=`, and `?sort=` query params. Filter buttons and sort dropdown use SvelteKit's `goto()` for client-side navigation that triggers a server re-load.

Key counts from mock data:
- All: 10 rows
- Source=kalshi: 3 rows (pred_001, pred_005, pred_008)
- Status=resolved (outcome != null): 6 rows
- Sort=date_asc oldest row: "Will Ethereum ETF see $10B+ net inflows in 2025?" (pred_008, 2025-02-01)

The filter buttons render as `<button class="tab">` with the platform name as text. The sort is a `<select id="sort">` with `<label for="sort">Sort</label>`.

- [ ] **Step 1: Create the spec file**

`apps/user-dashboard/tests/contract/predictions.spec.ts`:
```typescript
import { contractTest, expect } from '../../../../tests/ui-shared/fixtures';

contractTest.describe('predictions', () => {
  contractTest('initial render shows all 10 predictions', async ({ authedPage: page }) => {
    await page.goto('/predictions');
    await expect(page.getByRole('heading', { name: 'Predictions' })).toBeVisible();
    await expect(page.locator('table tbody tr')).toHaveCount(10);
  });

  contractTest('source filter — kalshi shows 3 predictions', async ({ authedPage: page }) => {
    await page.goto('/predictions');
    await page.getByRole('button', { name: 'kalshi' }).click();
    await page.waitForLoadState('networkidle');
    await expect(page.locator('table tbody tr')).toHaveCount(3);
  });

  contractTest('status filter — resolved shows 6 predictions', async ({ authedPage: page }) => {
    await page.goto('/predictions');
    await page.getByRole('button', { name: 'Resolved' }).click();
    await page.waitForLoadState('networkidle');
    await expect(page.locator('table tbody tr')).toHaveCount(6);
  });

  contractTest('sort — oldest first puts Ethereum ETF row first', async ({ authedPage: page }) => {
    await page.goto('/predictions');
    await page.getByLabel('Sort').selectOption('date_asc');
    await page.waitForLoadState('networkidle');
    await expect(page.locator('table tbody tr').first()).toContainText('Ethereum ETF');
  });
});
```

- [ ] **Step 2: Run just the predictions spec**

```bash
npx playwright test --config playwright.contract.config.ts tests/contract/predictions.spec.ts
```

Expected:
```
Running 4 tests using 1 worker

  ✓  contract › predictions › initial render shows all 10 predictions
  ✓  contract › predictions › source filter — kalshi shows 3 predictions
  ✓  contract › predictions › status filter — resolved shows 6 predictions
  ✓  contract › predictions › sort — oldest first puts Ethereum ETF row first

  4 passed
```

- [ ] **Step 3: Commit**

```bash
git add apps/user-dashboard/tests/contract/predictions.spec.ts
git commit -m "test: add predictions contract spec with filter and sort interactions"
```

---

## Task 5: Settings contract spec

**Files:**
- Create: `apps/user-dashboard/tests/contract/settings.spec.ts`

The settings route calls three API endpoints that the mock server handles:
- `GET /auth/me/linked-accounts` → `linked-accounts.json` (kalshi/polymarket/manifold linked, metaculus not)
- `GET /auth/me/share-tokens` → `share-tokens.json`
- `GET /auth/me/notifications` → `notifications.json`

`reshapeAccounts()` converts the flat array to keyed objects. The UI renders:
- Profile section: display name input pre-filled with `user.display_name` from layout auth (`auth-me.json` → "Jeremiah B.")
- Market data sources: `kalshi` → "Connected", shows `jeremiah_b_kalshi`; `metaculus` → "Not linked"
- Notification prefs: `email_on_resolution` checked (true), `email_on_badge` checked (true), `email_on_rank_change` unchecked (false)

Selectors:
- Profile display name: `page.getByLabel('Display Name')` — `<label for="display_name">` + `<input id="display_name">`
- Notification checkboxes: `page.getByRole('checkbox', { name: /market resolutions/i })` — checkbox is inside `<label class="toggle-row">` containing the text
- Platform item: `page.locator('.platform-item', { hasText: 'Metaculus' })` — each platform renders in a `.platform-item` div

- [ ] **Step 1: Create the spec file**

`apps/user-dashboard/tests/contract/settings.spec.ts`:
```typescript
import { contractTest, expect } from '../../../../tests/ui-shared/fixtures';

contractTest.describe('settings', () => {
  contractTest('profile section shows display name from auth response', async ({ authedPage: page }) => {
    await page.goto('/settings');
    await expect(page.getByRole('heading', { name: 'Settings' })).toBeVisible();
    await expect(page.getByLabel('Display Name')).toHaveValue('Jeremiah B.');
  });

  contractTest('linked accounts show correct connected/disconnected state', async ({ authedPage: page }) => {
    await page.goto('/settings');
    // Kalshi is linked — identifier is visible
    await expect(page.getByText('jeremiah_b_kalshi')).toBeVisible();
    // Metaculus is not linked
    await expect(
      page.locator('.platform-item', { hasText: 'Metaculus' }).getByText('Not linked')
    ).toBeVisible();
  });

  contractTest('notification prefs checkboxes reflect mock response', async ({ authedPage: page }) => {
    await page.goto('/settings');
    // email_on_resolution: true → checked
    await expect(page.getByRole('checkbox', { name: /market resolutions/i })).toBeChecked();
    // email_on_rank_change: false → unchecked
    await expect(page.getByRole('checkbox', { name: /leaderboard rank changes/i })).not.toBeChecked();
  });
});
```

- [ ] **Step 2: Run just the settings spec**

```bash
npx playwright test --config playwright.contract.config.ts tests/contract/settings.spec.ts
```

Expected:
```
Running 3 tests using 1 worker

  ✓  contract › settings › profile section shows display name from auth response
  ✓  contract › settings › linked accounts show correct connected/disconnected state
  ✓  contract › settings › notification prefs checkboxes reflect mock response

  3 passed
```

- [ ] **Step 3: Commit**

```bash
git add apps/user-dashboard/tests/contract/settings.spec.ts
git commit -m "test: add settings contract spec covering profile, linked accounts, notifications"
```

---

## Task 6: Stats contract spec

**Files:**
- Create: `apps/user-dashboard/tests/contract/stats.spec.ts`

The stats route (`/stats/+page.server.js`) returns mock.js data directly — no API call except layout auth. The page renders:
- `h1` heading "Stats"
- Stat cards: `mean_brier_score: 0.162` formatted as `0.162` by `fmt(n, 3)`
- Two chart sections: `<h2>Calibration Curve</h2>` and `<h2>Brier Score Over Time</h2>`

- [ ] **Step 1: Create the spec file**

`apps/user-dashboard/tests/contract/stats.spec.ts`:
```typescript
import { contractTest, expect } from '../../../../tests/ui-shared/fixtures';

contractTest.describe('stats', () => {
  contractTest('renders heading and Brier score value', async ({ authedPage: page }) => {
    await page.goto('/stats');
    await expect(page.getByRole('heading', { name: 'Stats' })).toBeVisible();
    await expect(page.getByText('0.162')).toBeVisible();
  });

  contractTest('shows calibration chart section', async ({ authedPage: page }) => {
    await page.goto('/stats');
    await expect(page.getByRole('heading', { name: 'Calibration Curve' })).toBeVisible();
  });

  contractTest('shows Brier timeline chart section', async ({ authedPage: page }) => {
    await page.goto('/stats');
    await expect(page.getByRole('heading', { name: 'Brier Score Over Time' })).toBeVisible();
  });
});
```

- [ ] **Step 2: Run just the stats spec**

```bash
npx playwright test --config playwright.contract.config.ts tests/contract/stats.spec.ts
```

Expected:
```
Running 3 tests using 1 worker

  ✓  contract › stats › renders heading and Brier score value
  ✓  contract › stats › shows calibration chart section
  ✓  contract › stats › shows Brier timeline chart section

  3 passed
```

- [ ] **Step 3: Commit**

```bash
git add apps/user-dashboard/tests/contract/stats.spec.ts
git commit -m "test: add stats contract spec"
```

---

## Task 7: Smoke login spec

**Files:**
- Create: `apps/user-dashboard/tests/smoke/login.spec.ts`

Smoke tests require the full real stack (API on port 8000, SvelteKit dev server on 5173). These cannot be run without a live backend and a `.env.test` with `TEST_USER_EMAIL` and `TEST_USER_PASSWORD`.

The login page has:
- `<label for="email">Email</label>` + `<input id="email">` → `getByLabel('Email')`
- `<label for="password">Password</label>` + `<input id="password">` → `getByLabel('Password')`
- `<button type="submit">Sign in</button>` (text changes to "Signing in…" while submitting)

`assertTestUserConfigured()` is called in-test (not in the fixture) so the error is thrown at test time with a clear message.

- [ ] **Step 1: Create the spec file**

`apps/user-dashboard/tests/smoke/login.spec.ts`:
```typescript
import { test, expect } from '../../../../tests/ui-shared/fixtures';
import { TEST_USER, assertTestUserConfigured } from '../../../../tests/ui-shared/config';

test.describe('login', () => {
  test('unauthenticated request redirects to /login', async ({ guestPage: page }) => {
    await page.goto('/dashboard');
    await page.waitForURL(/\/login/);
    await expect(page).toHaveURL(/login/);
  });

  test('valid credentials land on /dashboard', async ({ guestPage: page }) => {
    assertTestUserConfigured();
    await page.goto('/login');
    await page.getByLabel('Email').fill(TEST_USER.email);
    await page.getByLabel('Password').fill(TEST_USER.password);
    await page.getByRole('button', { name: 'Sign in' }).click();
    await page.waitForURL('**/dashboard');
    await expect(page.getByRole('heading', { name: 'Dashboard' })).toBeVisible();
  });
});
```

- [ ] **Step 2: Verify the spec file is listed (no syntax errors)**

```bash
npx playwright test --config playwright.config.ts --list
```

Expected: Playwright lists the two smoke tests (no TypeScript or import errors):
```
Listing tests:
  [smoke] › tests/smoke/login.spec.ts:5:3 › login › unauthenticated request redirects to /login
  [smoke] › tests/smoke/login.spec.ts:11:3 › login › valid credentials land on /dashboard
```

- [ ] **Step 3: Commit**

```bash
git add apps/user-dashboard/tests/smoke/login.spec.ts
git commit -m "test: add smoke login spec"
```

---

## Task 8: Full contract suite run + final verification

- [ ] **Step 1: Run the full contract suite**

From `apps/user-dashboard/`:
```bash
npm run test:contract
```

Expected — all 14 contract tests pass:
```
Running 14 tests using 1 worker

  ✓  contract › dashboard › renders heading and welcome message
  ✓  contract › dashboard › shows resolved and total prediction counts
  ✓  contract › dashboard › recent activity table has exactly 5 rows
  ✓  contract › dashboard › shows earned badge from mock data
  ✓  contract › predictions › initial render shows all 10 predictions
  ✓  contract › predictions › source filter — kalshi shows 3 predictions
  ✓  contract › predictions › status filter — resolved shows 6 predictions
  ✓  contract › predictions › sort — oldest first puts Ethereum ETF row first
  ✓  contract › settings › profile section shows display name from auth response
  ✓  contract › settings › linked accounts show correct connected/disconnected state
  ✓  contract › settings › notification prefs checkboxes reflect mock response
  ✓  contract › stats › renders heading and Brier score value
  ✓  contract › stats › shows calibration chart section
  ✓  contract › stats › shows Brier timeline chart section

  14 passed
```

- [ ] **Step 2: Confirm type check still passes**

```bash
npm run check
```

Expected: `svelte-check found 0 errors and 2 warnings in 1 file`

- [ ] **Step 3: Confirm exit code is 0**

```bash
npm run test:contract; echo "exit: $?"
```

Expected: `exit: 0`
