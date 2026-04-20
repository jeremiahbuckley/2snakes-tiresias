# DevBypass Mock Data Banner — Design Spec
**Date:** 2026-04-20
**Scope:** Add a persistent visual banner to `apps/user-dashboard` that appears when a developer is logged in via the devBypass flow. Add a contract test that verifies it.

---

## Problem

The `devBypass` action on `/login` sets `tiresias_token = 'dev-mock-token'`. This token does not validate against the real `/auth/me` endpoint. Currently, clicking devBypass on a local stack without the mock server running causes the layout auth check to fail and redirect back to `/login` — the bypass is broken in that context. With the mock server running (contract test environment), the token passes auth because the mock server accepts any token.

There is no visual indicator that tells a developer they are viewing mock data rather than live data. This can cause confusion — a developer thinks the dashboard is connected when it isn't.

---

## Architecture

Three files change:

| File | Change |
|---|---|
| `apps/user-dashboard/src/routes/+layout.server.js` | Detect `dev-mock-token`, skip `/auth/me` call, return `isMockSession: true` + hardcoded mock user |
| `apps/user-dashboard/src/routes/+layout.svelte` | Render persistent amber banner above `<slot />` when `data.isMockSession` is true |
| `apps/user-dashboard/tests/contract/devbypass.spec.ts` | Two contract tests: banner visible after devBypass, banner absent after normal login |

---

## Layout Server Change

In `+layout.server.js`, after reading the token cookie and before calling `/auth/me`, add:

```javascript
const DEV_TOKEN = 'dev-mock-token';

if (token === DEV_TOKEN && process.env.NODE_ENV !== 'production') {
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

This skips the `/auth/me` network call entirely, so devBypass works even when no backend is running. The `NODE_ENV !== 'production'` gate ensures the magic string check never activates in production builds. Child pages receive a valid `user` object with the same shape as the real API response.

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

No new mock server responses needed — `GET /auth/me` is already handled.

---

## Success Criteria

- Clicking "Continue with mock data (dev)" on `/login` lands on `/dashboard` with the amber banner visible
- Normal login (via mock server) shows no banner
- `npm run check` exits 0
- `npm run test:contract` exits 0 (all 16 tests pass: 14 existing + 2 new)
