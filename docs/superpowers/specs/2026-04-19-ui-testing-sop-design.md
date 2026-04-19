# UI Testing Architecture & SOP — Design Spec
**Date:** 2026-04-19
**Scope:** Playwright e2e testing for all three SvelteKit apps; guardrails for UI development workflow

---

## Problem Statement

Three SvelteKit apps (user-dashboard, public-leaderboard, public-profile) have no UI testing infrastructure. Without a shared config layer, tests sprawl into per-file hardcoded URLs, ports, credentials, and repeated fixture setup — each file becomes its own source of truth and drifts independently. This design establishes a single shared package, a two-suite test model, per-app CLAUDE.md additions, and a Superpowers skill that enforces the SOP.

---

## Architecture

### Directory Layout

```
tests/
  ui-shared/                  ← shared by all three apps
    config.ts                 ← BASE_URLS + TEST_USER from env vars only
    fixtures.ts               ← Playwright fixture factory (authedPage, guestPage)
    api-mocks/
      handlers.ts             ← page.route() mock handlers for contract suite
      responses/              ← JSON response fixtures (not inlined in tests)
    helpers/
      auth.ts                 ← login(), logout() page helpers
  e2e/                        ← existing Python e2e (unchanged)
  integration/                ← existing Python integration (unchanged)

apps/
  user-dashboard/
    tests/
      smoke/                  ← local suite, requires real stack
      contract/               ← CI suite, uses api-mocks from ui-shared
    playwright.config.ts      ← imports from tests/ui-shared/config.ts
  public-leaderboard/
    tests/ ...                ← added when app is implemented
    playwright.config.ts
  public-profile/
    tests/ ...                ← added when app is implemented
    playwright.config.ts
```

**Invariant:** if a value appears in more than one test file, it belongs in `tests/ui-shared/`. App-level test files contain only scenario logic.

---

## Config & Env Var Management

### `.env.test.example` (committed, at repo root)

```
DASHBOARD_URL=http://localhost:5173
LEADERBOARD_URL=http://localhost:5174
PROFILE_URL=http://localhost:5175
API_BASE_URL=http://localhost:8000
TEST_USER_EMAIL=testuser@example.com
TEST_USER_PASSWORD=test-password-local
```

`.env.test` is gitignored. CI injects these as environment variables directly.

### `tests/ui-shared/config.ts`

```ts
export const BASE_URLS = {
  dashboard: process.env.DASHBOARD_URL ?? 'http://localhost:5173',
  leaderboard: process.env.LEADERBOARD_URL ?? 'http://localhost:5174',
  profile: process.env.PROFILE_URL ?? 'http://localhost:5175',
  api: process.env.API_BASE_URL ?? 'http://localhost:8000',
};

export const TEST_USER = {
  email: process.env.TEST_USER_EMAIL!,
  password: process.env.TEST_USER_PASSWORD!,
};
```

**Rule:** `process.env` is accessed **only** in `config.ts`. All other files import from `config.ts`.

### Per-app `playwright.config.ts` pattern

```ts
import { defineConfig } from '@playwright/test';
import { BASE_URLS } from '../../tests/ui-shared/config';

export default defineConfig({
  projects: [
    {
      name: 'smoke',
      use: { baseURL: BASE_URLS.dashboard },
      testDir: './tests/smoke',
    },
    {
      name: 'contract',
      use: { baseURL: BASE_URLS.dashboard },
      testDir: './tests/contract',
    },
  ],
});
```

---

## Two-Suite Model

### Smoke Suite (`--project=smoke`)

- Requires the real local stack (FastAPI + Postgres + dev server)
- No API mocking — tests hit the real backend
- Uses `TEST_USER` credentials for real authenticated sessions
- Covers critical user paths end-to-end
- Run by developers before marking UI work done

### Contract Suite (`--project=contract`)

- No backend required — CI-safe
- Uses `page.route()` to intercept all calls to `API_BASE_URL` and return canned responses from `tests/ui-shared/api-mocks/responses/`
- Tests that UI renders correctly given known API response shapes
- Runs against `vite preview` build of the app (requires `npm run build` first; CI handles this as a pre-step)
- Run in CI pipeline

CI runs only the contract suite. The smoke suite is a developer gate enforced by the skill and CLAUDE.md.

---

## Fixtures & Test-User Factory

### `tests/ui-shared/fixtures.ts`

```ts
import { test as base, type Page } from '@playwright/test';
import { TEST_USER } from './config';
import { login } from './helpers/auth';

export const test = base.extend<{
  authedPage: Page;
  guestPage: Page;
}>({
  authedPage: async ({ page }, use) => {
    await login(page, TEST_USER.email, TEST_USER.password);
    await use(page);
  },
  guestPage: async ({ page }, use) => {
    await use(page);
  },
});

export { expect } from '@playwright/test';
```

The contract suite uses a separate `contractTest` fixture exported from `fixtures.ts` that extends `test` and registers all `api-mocks/handlers.ts` routes via `page.route()` before `use()`. Spec files in `tests/contract/` import `contractTest` instead of `test`.

### Usage in spec files

```ts
// apps/user-dashboard/tests/smoke/dashboard.spec.ts
import { test, expect } from '../../../../tests/ui-shared/fixtures';

test('shows prediction history', async ({ authedPage }) => {
  await authedPage.goto('/dashboard');
  await expect(authedPage.getByRole('heading', { name: 'Dashboard' })).toBeVisible();
});
```

Spec files **never** import from `@playwright/test` directly.

---

## Anti-Patterns (Enforced by Skill + CLAUDE.md)

| Pattern | Instead |
|---|---|
| `'http://localhost:5173'` in a test file | `BASE_URLS.dashboard` from `config.ts` |
| `process.env.WHATEVER` in a test file | Import from `config.ts` |
| `beforeEach` login block in a spec file | Use `authedPage` fixture |
| `import { test } from '@playwright/test'` in a spec | Import from `tests/ui-shared/fixtures` |
| `page.goto('/login')` in a spec file | Handled by `authedPage` fixture setup |
| Credential strings in spec files | `TEST_USER` from `config.ts` |
| Inline JSON response data in contract tests | JSON files in `api-mocks/responses/` |

---

## CLAUDE.md Additions

### `apps/user-dashboard/CLAUDE.md` — new Testing section

```markdown
## Testing

Before marking any UI work done, run all three checks in order:

1. **Type check**: `npm run check` — must pass with zero errors
2. **Smoke tests**: `npx playwright test --project=smoke` (requires full local stack)
3. **Contract tests**: `npx playwright test --project=contract` (no backend needed)

### Anti-patterns — never do these
- Hardcode `localhost`, port numbers, or base URLs in test files
- Define `beforeEach` login flows in spec files
- Import `test` or `expect` from `@playwright/test` directly in spec files
- Add credential strings to spec files

### Shared test utilities
All fixtures, config, and API mock handlers live in `tests/ui-shared/`.
Import from there, never define duplicates app-side.

### Running tests
# From the app directory:
npx playwright test --project=smoke      # local, needs real stack
npx playwright test --project=contract   # CI-safe, no backend
```

`public-leaderboard` and `public-profile` get the same section when their test suites are built (no `authedPage` needed — public apps use `guestPage` only).

---

## Superpowers Skill: `ui-dev`

**Location:** `~/.claude/plugins/local/ui-dev/SKILL.md` (local plugin, not in repo)

**Trigger:** Any task touching `.svelte` files, files in `apps/`, or files in `tests/ui-shared/`.

### Enforced SOP sequence

1. Confirm the relevant server is responding before writing UI code: dev server (`npm run dev`) for smoke work, preview server (`npm run build && npm run preview`) for contract work
2. Run `svelte-check` — no UI work proceeds on a type-erroring codebase
3. Before writing any test file, grep for anti-pattern violations (see table above)
4. After implementation, run `npm run check` then `npx playwright test --project=contract`
5. Before claiming done, quote the actual terminal output — no summarizing a passing run

### Hard gates (cannot be skipped or rationalized away)

- No URL string literals in test files outside `config.ts`
- No credential strings in test files outside `config.ts`
- No `page.goto('/login')` in spec files (must go through `authedPage` fixture)
- `svelte-check` must exit 0 before any UI work is reported complete
- Smoke tests must pass before a UI feature is marked done in a dev session

---

## Implementation Scope & Sequence

**Phase 1 (this plan):** Infrastructure and guardrails only — no application tests yet.
- `tests/ui-shared/` with `config.ts`, `fixtures.ts`, `helpers/auth.ts`, `api-mocks/` skeleton
- `.env.test.example` at repo root
- `apps/user-dashboard/playwright.config.ts`
- CLAUDE.md additions for user-dashboard
- `ui-dev` Superpowers skill

**Phase 2:** First smoke tests for user-dashboard (login, dashboard load, predictions page).

**Phase 3:** First contract tests for user-dashboard (dashboard renders with mocked API responses).

**Phase 4:** Expand to public-leaderboard and public-profile as those apps are implemented.

Phase 2+ are separate implementation plans.
