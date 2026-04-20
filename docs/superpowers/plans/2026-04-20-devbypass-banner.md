# DevBypass Mock Data Banner Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a persistent amber banner to `user-dashboard` that appears when a developer is logged in via the devBypass flow, and gate all devBypass behaviour behind an explicit `DEV_BYPASS_ENABLED` env var.

**Architecture:** The layout server detects the `dev-mock-token` cookie value (only when `DEV_BYPASS_ENABLED=true`) and returns `isMockSession: true` + a hardcoded mock user, skipping the real `/auth/me` call. The layout component renders an amber banner when that flag is set. The login page's `load()` exposes `devBypassEnabled` so the button is hidden in environments where the flag is off.

**Tech Stack:** SvelteKit 2, Svelte 4, Playwright 1.44, Node.js process.env

---

## File Map

| Action | Path |
|---|---|
| Modify | `apps/user-dashboard/src/routes/login/+page.server.js` |
| Modify | `apps/user-dashboard/src/routes/login/+page.svelte` |
| Modify | `apps/user-dashboard/playwright.contract.config.ts` |
| Modify | `apps/user-dashboard/src/routes/+layout.server.js` |
| Modify | `apps/user-dashboard/src/routes/+layout.svelte` |
| Create | `apps/user-dashboard/tests/contract/devbypass.spec.ts` |

---

## Task 1: Gate devBypass behind DEV_BYPASS_ENABLED

**Files:**
- Modify: `apps/user-dashboard/src/routes/login/+page.server.js`
- Modify: `apps/user-dashboard/src/routes/login/+page.svelte`
- Modify: `apps/user-dashboard/playwright.contract.config.ts`

- [ ] **Step 1: Update `login/+page.server.js`**

Replace the entire file with:

```javascript
import { redirect, fail } from '@sveltejs/kit';

const API_BASE = process.env.API_BASE_URL ?? 'http://localhost:8000';

/** @type {import('./$types').PageServerLoad} */
export async function load() {
  return { devBypassEnabled: process.env.DEV_BYPASS_ENABLED === 'true' };
}

/** @type {import('./$types').Actions} */
export const actions = {
  /** Real login: POST /auth/login → set JWT cookie. */
  login: async ({ request, cookies, url, fetch }) => {
    const data = await request.formData();
    const email = data.get('email')?.toString() ?? '';
    const password = data.get('password')?.toString() ?? '';

    let result;
    try {
      const res = await fetch(`${API_BASE}/auth/login`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ email, password }),
      });
      if (res.status === 401) return fail(400, { error: 'Incorrect email or password.' });
      if (!res.ok) throw new Error(`API ${res.status}`);
      result = await res.json();
    } catch {
      return fail(500, { error: 'Could not reach the API. Is the server running?' });
    }
    cookies.set('tiresias_token', result.access_token, {
      path: '/',
      httpOnly: true,
      sameSite: 'lax',
      maxAge: 60 * 60 * 24 * 7,
      secure: process.env.NODE_ENV === 'production',
    });

    const redirectTo = url.searchParams.get('redirect') ?? '/dashboard';
    throw redirect(303, redirectTo);
  },

  devBypass: async ({ cookies, url }) => {
    if (process.env.DEV_BYPASS_ENABLED !== 'true') {
      return fail(403, { error: 'Dev bypass is not enabled.' });
    }
    cookies.set('tiresias_token', 'dev-mock-token', {
      path: '/',
      httpOnly: true,
      sameSite: 'lax',
      maxAge: 60 * 60 * 24,
    });
    const redirectTo = url.searchParams.get('redirect') ?? '/dashboard';
    throw redirect(303, redirectTo);
  },

  /** Sign out: clear the token cookie. */
  logout: async ({ cookies }) => {
    cookies.delete('tiresias_token', { path: '/' });
    throw redirect(303, '/login');
  },
};
```

- [ ] **Step 2: Update `login/+page.svelte` — add `export let data` and gate the button**

In the `<script>` block, add `export let data` after `export let form`:

```svelte
<script>
  import { enhance } from '$app/forms';

  /** @type {import('./$types').PageData} */
  export let data;
  /** @type {import('./$types').ActionData} */
  export let form;

  let loading = false;
</script>
```

Replace the unconditional divider + devBypass form block:

```svelte
    <div class="divider">or</div>

    <form method="POST" action="?/devBypass">
      <button type="submit" class="btn btn-secondary">
        Continue with mock data (dev)
      </button>
    </form>
```

With a conditional block:

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

- [ ] **Step 3: Add `DEV_BYPASS_ENABLED` to the contract webServer env**

In `apps/user-dashboard/playwright.contract.config.ts`, update the second webServer entry's `env`:

```typescript
    {
      command: 'npm run dev -- --port 5181',
      env: { API_BASE_URL: 'http://localhost:8001', PUBLIC_API_BASE_URL: 'http://localhost:8001', DEV_BYPASS_ENABLED: 'true' },
      url: 'http://localhost:5181',
      reuseExistingServer: !process.env.CI,
    },
```

- [ ] **Step 4: Verify type check passes**

```bash
cd apps/user-dashboard && npm run check
```

Expected: `svelte-check found 0 errors and 2 warnings in 1 file`

- [ ] **Step 5: Commit**

```bash
git add apps/user-dashboard/src/routes/login/+page.server.js \
        apps/user-dashboard/src/routes/login/+page.svelte \
        apps/user-dashboard/playwright.contract.config.ts
git commit -m "feat: gate devBypass behind DEV_BYPASS_ENABLED env var"
```

---

## Task 2: Mock session detection + banner

**Files:**
- Modify: `apps/user-dashboard/src/routes/+layout.server.js`
- Modify: `apps/user-dashboard/src/routes/+layout.svelte`

- [ ] **Step 1: Update `+layout.server.js` — detect dev-mock-token**

Replace the entire file with:

```javascript
import { redirect } from '@sveltejs/kit';

const PUBLIC_ROUTES = ['/login', '/register'];
const API_BASE = process.env.API_BASE_URL ?? 'http://localhost:8000';
const DEV_TOKEN = 'dev-mock-token';

/** @type {import('./$types').LayoutServerLoad} */
export async function load({ url, cookies, fetch }) {
  const path = url.pathname;

  if (PUBLIC_ROUTES.some((r) => path.startsWith(r))) {
    return {};
  }

  const token = cookies.get('tiresias_token');

  if (!token) {
    throw redirect(303, `/login?redirect=${encodeURIComponent(path)}`);
  }

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

  const res = await fetch(`${API_BASE}/auth/me`, {
    headers: { Authorization: `Bearer ${token}` },
  });

  if (!res.ok) {
    cookies.delete('tiresias_token', { path: '/' });
    throw redirect(303, `/login?redirect=${encodeURIComponent(path)}`);
  }

  const user = await res.json();
  return { token, user };
}
```

- [ ] **Step 2: Update `+layout.svelte` — add banner**

In the `<script>` block, add `export let data` after the existing imports:

```svelte
<script>
  import { page } from '$app/stores';

  export let data;

  const navItems = [
    { href: '/dashboard', label: 'Dashboard', icon: '⬛' },
    { href: '/predictions', label: 'Predictions', icon: '📋' },
    { href: '/stats', label: 'Stats', icon: '📈' },
    { href: '/settings', label: 'Settings', icon: '⚙️' },
  ];

  $: currentPath = $page.url.pathname;

  function isActive(href) {
    return currentPath === href || currentPath.startsWith(href + '/');
  }
</script>
```

In the template, find the `<main class="main">` element and add the banner before `<slot />`:

```svelte
  <!-- Main content -->
  <main class="main">
    {#if data.isMockSession}
      <div class="mock-banner">
        ⚠ Mock data mode — not connected to real backend
      </div>
    {/if}
    <slot />
  </main>
```

In the `<style>` block, add the `.mock-banner` rule before the closing `</style>` tag:

```css
  .mock-banner {
    background: #fef3c7;
    border: 1px solid #f59e0b;
    color: #92400e;
    padding: 10px 16px;
    border-radius: 6px;
    font-size: 13px;
    font-weight: 500;
    margin-bottom: 24px;
  }
```

- [ ] **Step 3: Verify type check passes**

```bash
npm run check
```

Expected: `svelte-check found 0 errors and 2 warnings in 1 file`

- [ ] **Step 4: Commit**

```bash
git add apps/user-dashboard/src/routes/+layout.server.js \
        apps/user-dashboard/src/routes/+layout.svelte
git commit -m "feat: add mock session detection and amber banner to layout"
```

---

## Task 3: Contract tests + full suite run

**Files:**
- Create: `apps/user-dashboard/tests/contract/devbypass.spec.ts`

- [ ] **Step 1: Create the spec file**

`apps/user-dashboard/tests/contract/devbypass.spec.ts`:

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

- [ ] **Step 2: Run just the devbypass spec**

```bash
npx playwright test --config playwright.contract.config.ts tests/contract/devbypass.spec.ts
```

Expected:
```
Running 2 tests using 1 worker

  ✓  contract › devBypass banner › shows mock data banner after devBypass login
  ✓  contract › devBypass banner › does not show banner after normal login

  2 passed
```

- [ ] **Step 3: Run the full contract suite**

```bash
npm run test:contract
```

Expected — all 16 tests pass:
```
Running 16 tests using 4 workers
  ...
  16 passed
```

- [ ] **Step 4: Confirm type check still passes**

```bash
npm run check
```

Expected: `svelte-check found 0 errors and 2 warnings in 1 file`

- [ ] **Step 5: Commit**

```bash
git add apps/user-dashboard/tests/contract/devbypass.spec.ts
git commit -m "test: add devBypass banner contract spec"
```
