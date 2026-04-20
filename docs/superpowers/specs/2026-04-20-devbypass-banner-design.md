# DevBypass Mock Data Banner — Design Spec
**Date:** 2026-04-20
**Scope:** Add a persistent visual banner to `apps/user-dashboard` that appears when a developer is logged in via the devBypass flow. Gate all devBypass behaviour behind a `DEV_BYPASS_ENABLED` env var. Add a contract test that verifies the banner.

---

## Problem

The `devBypass` action on `/login` sets `tiresias_token = 'dev-mock-token'`. This token does not validate against the real `/auth/me` endpoint. Currently, clicking devBypass on a local stack without the mock server running causes the layout auth check to fail and redirect back to `/login` — the bypass is broken in that context. With the mock server running (contract test environment), the token passes auth because the mock server accepts any token.

There is no visual indicator that tells a developer they are viewing mock data rather than live data. This can cause confusion — a developer thinks the dashboard is connected when it isn't.

### Security concerns with the original approach

Gating on `NODE_ENV !== 'production'` is unreliable: Node.js defaults `NODE_ENV` to `'development'` if not explicitly set, so a production deployment that omits `NODE_ENV=production` would expose the bypass to anyone who knows the magic cookie value. The magic string is in the public git history, making it discoverable. Additionally, the devBypass button on `/login` renders unconditionally in all environments, revealing dev infrastructure in production.

---

## Architecture

Five files change:

| File | Change |
|---|---|
| `apps/user-dashboard/src/routes/+layout.server.js` | Detect `dev-mock-token` when `DEV_BYPASS_ENABLED=true`, skip `/auth/me` call, return `isMockSession: true` + hardcoded mock user |
| `apps/user-dashboard/src/routes/+layout.svelte` | Render persistent amber banner above `<slot />` when `data.isMockSession` is true |
| `apps/user-dashboard/src/routes/login/+page.server.js` | Add `load()` that returns `devBypassEnabled` flag; `devBypass` action checks it and returns 403 if not set |
| `apps/user-dashboard/src/routes/login/+page.svelte` | Conditionally render the "Continue with mock data (dev)" button based on `data.devBypassEnabled` |
| `apps/user-dashboard/tests/contract/devbypass.spec.ts` | Two contract tests: banner visible after devBypass, banner absent after normal login |

The `DEV_BYPASS_ENABLED=true` env var must be explicitly set to enable the feature. It is not set in `.env` (default dev config) — developers opt in intentionally. It is set in the contract test webServer env (`playwright.contract.config.ts`).

---

## Layout Server Change

In `+layout.server.js`, after reading the token cookie and before calling `/auth/me`:

```javascript
const DEV_TOKEN = 'dev-mock-token';

if (token === DEV_TOKEN && process.env.DEV_BYPASS_ENABLED === 'true') {
  return {
    token,
    isMockSession: true,
    user: {
      id: 'dev',
      username: 'dev',
      display_name: 'Dev User',
      email: 'dev@localhost',
      bio: null,
      avatar_url: null,
      social_links: {},
    },
  };
}
```

This skips the `/auth/me` network call entirely, so devBypass works even when no backend is running. The `DEV_BYPASS_ENABLED` gate ensures production is safe by default even if `NODE_ENV` is not set. Child pages receive a valid `user` object with the same shape as the real API response.

---

## Login Page Changes

Add a `load()` function to `login/+page.server.js` that exposes the flag:

```javascript
export async function load() {
  return { devBypassEnabled: process.env.DEV_BYPASS_ENABLED === 'true' };
}
```

Guard the `devBypass` action so it cannot be triggered even via direct POST if the flag is off:

```javascript
devBypass: async ({ cookies, url }) => {
  if (process.env.DEV_BYPASS_ENABLED !== 'true') {
    return fail(403, { error: 'Dev bypass is not enabled.' });
  }
  // ... rest of action unchanged
},
```

In `login/+page.svelte`, gate the button on `data.devBypassEnabled`:

```svelte
{#if data.devBypassEnabled}
  <div class="divider">or</div>
  <form method="POST" action="?/devBypass">
    <button type="submit" class="btn btn-secondary">
      Continue with mock data (dev)
    </button>
  </form>
{/if}
```

---

## Banner

In `+layout.svelte`, add `export let data` to the script block (currently absent — the layout doesn't use server data yet), then render inside `.main` above `<slot />`:

```svelte
{#if data.isMockSession}
  <div class="mock-banner">
    ⚠ Mock data mode — not connected to real backend
  </div>
{/if}
```

- Full-width bar, amber background (`#fef3c7`), amber border (`#f59e0b`), dark amber text (`#92400e`)
- No dismiss button — persists until sign-out
- Only appears on protected pages (the layout's `load()` returns early for `/login` and `/register`, so `data.isMockSession` is undefined there)

---

## Contract Config Change

Add `DEV_BYPASS_ENABLED: 'true'` to the SvelteKit webServer env in `playwright.contract.config.ts`:

```typescript
{
  command: 'npm run dev -- --port 5181',
  env: { API_BASE_URL: 'http://localhost:8001', PUBLIC_API_BASE_URL: 'http://localhost:8001', DEV_BYPASS_ENABLED: 'true' },
  url: 'http://localhost:5181',
  reuseExistingServer: !process.env.CI,
},
```

---

## Contract Tests

**File:** `apps/user-dashboard/tests/contract/devbypass.spec.ts`

```typescript
import { contractTest, expect } from '../../../../tests/ui-shared/fixtures';

contractTest.describe('devBypass banner', () => {
  contractTest('shows mock data banner after devBypass login', async ({ guestPage: page }) => {
    await page.goto('/login');
    await page.getByRole('button', { name: /continue with mock data/i }).click();
    await page.waitForURL('/dashboard');
    await expect(page.getByText(/mock data mode/i)).toBeVisible();
  });

  contractTest('does not show banner after normal login', async ({ authedPage: page }) => {
    await page.goto('/dashboard');
    await expect(page.getByText(/mock data mode/i)).not.toBeVisible();
  });
});
```

No new mock server responses needed — `GET /auth/me` is already handled. The devBypass test uses `guestPage` (no pre-login) and clicks the button directly.

---

## Success Criteria

- `DEV_BYPASS_ENABLED` not set → devBypass button hidden, action returns 403, layout never enters mock session
- `DEV_BYPASS_ENABLED=true` → button visible, clicking it shows amber banner on all protected pages
- Normal login (via mock server) shows no banner
- `npm run check` exits 0
- `npm run test:contract` exits 0 (all 16 tests pass: 14 existing + 2 new)
