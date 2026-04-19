# UI Testing Infrastructure — Phase 1 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Lay the shared config/fixture layer, two-suite Playwright config for user-dashboard, CLAUDE.md guardrails, and ui-dev skill — zero application tests, all infrastructure.

**Architecture:** A `tests/ui-shared/` package provides the single source of truth for base URLs and test credentials (read from `.env.test` via dotenv). Per-app `playwright.config.ts` files import from this shared package and define two Playwright projects: `smoke` (requires real stack) and `contract` (API mocked, CI-safe). The ui-dev skill enforces the SOP.

**Tech Stack:** @playwright/test ^1.44, dotenv ^16, TypeScript, SvelteKit 2, Svelte 4, Node 20+

---

## File Map

| Action | Path | Responsibility |
|---|---|---|
| Create | `tests/ui-shared/package.json` | Declares `dotenv` + `@playwright/test` as dev deps for the shared package |
| Create | `tests/ui-shared/config.ts` | Loads `.env.test`, exports `BASE_URLS` and `TEST_USER` — the only place `process.env` is accessed |
| Create | `tests/ui-shared/helpers/auth.ts` | `login()` and `logout()` Playwright page helpers |
| Create | `tests/ui-shared/fixtures.ts` | Exports `test`, `contractTest`, `expect` — the only imports spec files need |
| Create | `tests/ui-shared/api-mocks/handlers.ts` | `registerApiMocks()` — wires `page.route()` to mock response files |
| Create | `tests/ui-shared/api-mocks/responses/.gitkeep` | Placeholder dir for per-route JSON fixtures |
| Create | `.env.test.example` | Committed template with all required env var names and safe default values |
| Modify | `.gitignore` | Add `!.env.test.example` so the example file is not gitignored by the existing `.env.*` rule |
| Modify | `apps/user-dashboard/package.json` | Add `@playwright/test` to `devDependencies` |
| Create | `apps/user-dashboard/playwright.config.ts` | Two-project Playwright config importing from `tests/ui-shared/config` |
| Create | `apps/user-dashboard/tests/smoke/.gitkeep` | Placeholder for smoke specs |
| Create | `apps/user-dashboard/tests/contract/.gitkeep` | Placeholder for contract specs |
| Modify | `apps/user-dashboard/CLAUDE.md` | Add Testing section with required checks and anti-patterns |
| Create | `~/.claude/skills/ui-dev/SKILL.md` | Superpowers skill enforcing the UI dev SOP |

---

## Task 1: Create shared package manifest and install deps

**Files:**
- Create: `tests/ui-shared/package.json`
- Run: `npm install` in `tests/ui-shared/`

- [ ] **Step 1: Create `tests/ui-shared/package.json`**

```json
{
  "name": "ui-shared",
  "private": true,
  "type": "module",
  "devDependencies": {
    "@playwright/test": "^1.44.0",
    "dotenv": "^16.4.0"
  }
}
```

- [ ] **Step 2: Install dependencies**

```bash
cd tests/ui-shared && npm install
```

Expected: `node_modules/` created containing `dotenv` and `@playwright/test`. No errors.

- [ ] **Step 3: Verify dotenv resolves from the shared package**

```bash
node --input-type=module <<'EOF'
import dotenv from 'dotenv';
console.log('dotenv version:', dotenv.parse('FOO=bar').FOO);
EOF
```

Run this from `tests/ui-shared/`. Expected output: `dotenv version: bar`

- [ ] **Step 4: Commit**

```bash
git add tests/ui-shared/package.json tests/ui-shared/package-lock.json
git commit -m "chore: add ui-shared package with playwright and dotenv"
```

---

## Task 2: Create env var config layer

**Files:**
- Create: `.env.test.example`
- Create: `tests/ui-shared/config.ts`
- Modify: `.gitignore`

- [ ] **Step 1: Create `.env.test.example` at repo root**

```bash
# .env.test.example
# Copy to .env.test and fill in values for local UI testing.
# CI injects these as environment variables directly.

DASHBOARD_URL=http://localhost:5173
LEADERBOARD_URL=http://localhost:5174
PROFILE_URL=http://localhost:5175
API_BASE_URL=http://localhost:8000
TEST_USER_EMAIL=testuser@example.com
TEST_USER_PASSWORD=test-password-local
```

Create as a plain file (not a bash heredoc syntax file) at the repo root.

- [ ] **Step 2: Add `!.env.test.example` to `.gitignore`**

The repo `.gitignore` already has `.env.*` which would gitignore `.env.test.example`. Add the exception immediately after the existing `!.env.example` line:

Before (in `.gitignore`):
```
.env
.env.*
!.env.example
```

After:
```
.env
.env.*
!.env.example
!.env.test.example
```

- [ ] **Step 3: Create `tests/ui-shared/config.ts`**

```ts
import dotenv from 'dotenv';
import { dirname, resolve } from 'path';
import { fileURLToPath } from 'url';

const __dirname = dirname(fileURLToPath(import.meta.url));
dotenv.config({ path: resolve(__dirname, '../../.env.test') });

export const BASE_URLS = {
  dashboard: process.env.DASHBOARD_URL ?? 'http://localhost:5173',
  leaderboard: process.env.LEADERBOARD_URL ?? 'http://localhost:5174',
  profile: process.env.PROFILE_URL ?? 'http://localhost:5175',
  api: process.env.API_BASE_URL ?? 'http://localhost:8000',
} as const;

export const TEST_USER = {
  email: process.env.TEST_USER_EMAIL ?? '',
  password: process.env.TEST_USER_PASSWORD ?? '',
} as const;
```

Note: `dotenv.config()` is called before the constants are defined. If `.env.test` does not exist (e.g., in CI), dotenv silently skips it and the variables fall through to defaults or CI-injected values — this is correct behavior.

- [ ] **Step 4: Verify config imports correctly**

```bash
cd tests/ui-shared && node --input-type=module <<'EOF'
import { BASE_URLS, TEST_USER } from './config.ts';
console.log('dashboard URL:', BASE_URLS.dashboard);
console.log('has TEST_USER shape:', 'email' in TEST_USER && 'password' in TEST_USER);
EOF
```

Expected:
```
dashboard URL: http://localhost:5173
has TEST_USER shape: true
```

- [ ] **Step 5: Commit**

```bash
git add .env.test.example .gitignore tests/ui-shared/config.ts
git commit -m "feat: add ui-shared config layer with env-var-driven BASE_URLS and TEST_USER"
```

---

## Task 3: Create auth helper

**Files:**
- Create: `tests/ui-shared/helpers/auth.ts`

The `login` helper navigates to `/login`, fills the email and password fields, submits the form, and waits for the redirect to `/dashboard`. The exact selectors assume the login form uses accessible labels — verify and adjust during Phase 2 smoke testing if the form uses different aria attributes.

- [ ] **Step 1: Create `tests/ui-shared/helpers/auth.ts`**

```ts
import type { Page } from '@playwright/test';

export async function login(page: Page, email: string, password: string): Promise<void> {
  await page.goto('/login');
  await page.getByLabel('Email').fill(email);
  await page.getByLabel('Password').fill(password);
  await page.getByRole('button', { name: /log in/i }).click();
  await page.waitForURL('/dashboard');
}

export async function logout(page: Page): Promise<void> {
  await page.getByRole('button', { name: /log out/i }).click();
  await page.waitForURL('/login');
}
```

- [ ] **Step 2: Verify TypeScript compiles**

```bash
cd tests/ui-shared && npx tsc --noEmit --strict --moduleResolution bundler --module esnext helpers/auth.ts
```

Expected: no output (exit 0). If it fails, check that `@playwright/test` types are present in `node_modules/@playwright/test`.

- [ ] **Step 3: Commit**

```bash
git add tests/ui-shared/helpers/auth.ts
git commit -m "feat: add shared login/logout helpers for Playwright smoke tests"
```

---

## Task 4: Create shared fixture factory

**Files:**
- Create: `tests/ui-shared/fixtures.ts`

Exports three things spec files need: `test` (smoke fixture with real auth), `contractTest` (contract fixture with auth + API mocks registered), and `expect` (re-exported from `@playwright/test`). Spec files import only from this file, never from `@playwright/test` directly.

- [ ] **Step 1: Create `tests/ui-shared/fixtures.ts`**

```ts
import { test as base, type Page } from '@playwright/test';
import { TEST_USER } from './config';
import { login } from './helpers/auth';
import { registerApiMocks } from './api-mocks/handlers';

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

// contractTest registers API mocks before any page interaction.
// When writing the first contract test that uses authedPage, you must also
// add a mock for the POST /auth/login endpoint in handlers.ts — otherwise
// the login() call inside authedPage will try to hit the real API.
export const contractTest = base.extend<{
  authedPage: Page;
  guestPage: Page;
}>({
  authedPage: async ({ page }, use) => {
    await registerApiMocks(page);
    await login(page, TEST_USER.email, TEST_USER.password);
    await use(page);
  },
  guestPage: async ({ page }, use) => {
    await registerApiMocks(page);
    await use(page);
  },
});

export { expect } from '@playwright/test';
```

- [ ] **Step 2: Commit**

```bash
git add tests/ui-shared/fixtures.ts
git commit -m "feat: add shared Playwright fixture factory (test, contractTest, expect)"
```

---

## Task 5: Create API mocks skeleton

**Files:**
- Create: `tests/ui-shared/api-mocks/handlers.ts`
- Create: `tests/ui-shared/api-mocks/responses/.gitkeep`

The `registerApiMocks` function intercepts all calls to `BASE_URLS.api` and routes them to JSON files in `api-mocks/responses/`. The `pathToMockFile` map starts empty — entries are added in Phase 3 when contract tests are written.

- [ ] **Step 1: Create `tests/ui-shared/api-mocks/handlers.ts`**

```ts
import type { Page } from '@playwright/test';
import { BASE_URLS } from '../config';
import { resolve, dirname } from 'path';
import { fileURLToPath } from 'url';

const __dirname = dirname(fileURLToPath(import.meta.url));

const pathToMockFile: Record<string, string> = {
  // Add entries here as you build the contract suite.
  // Key: API pathname (e.g. '/auth/me')
  // Value: filename inside api-mocks/responses/ (e.g. 'auth-me.json')
  // Example:
  //   '/auth/me': 'auth-me.json',
};

export async function registerApiMocks(page: Page): Promise<void> {
  await page.route(`${BASE_URLS.api}/**`, async (route) => {
    const url = new URL(route.request().url());
    const mockFilename = pathToMockFile[url.pathname];
    if (mockFilename) {
      await route.fulfill({
        path: resolve(__dirname, 'responses', mockFilename),
        contentType: 'application/json',
      });
    } else {
      await route.fulfill({
        status: 404,
        contentType: 'application/json',
        body: JSON.stringify({ detail: `no mock for ${url.pathname}` }),
      });
    }
  });
}
```

- [ ] **Step 2: Create `tests/ui-shared/api-mocks/responses/.gitkeep`**

Create an empty file at `tests/ui-shared/api-mocks/responses/.gitkeep` so the directory is tracked by git.

- [ ] **Step 3: Commit**

```bash
git add tests/ui-shared/api-mocks/handlers.ts tests/ui-shared/api-mocks/responses/.gitkeep
git commit -m "feat: add API mocks skeleton for contract test suite"
```

---

## Task 6: Install Playwright and configure user-dashboard

**Files:**
- Modify: `apps/user-dashboard/package.json`
- Create: `apps/user-dashboard/playwright.config.ts`
- Create: `apps/user-dashboard/tests/smoke/.gitkeep`
- Create: `apps/user-dashboard/tests/contract/.gitkeep`

- [ ] **Step 1: Add `@playwright/test` to user-dashboard devDependencies**

Edit `apps/user-dashboard/package.json`. Add `@playwright/test` and `playwright` to `devDependencies`:

```json
{
  "name": "user-dashboard",
  "version": "0.0.1",
  "private": true,
  "type": "module",
  "scripts": {
    "dev": "vite dev",
    "build": "vite build",
    "preview": "vite preview",
    "check": "svelte-kit sync && svelte-check --tsconfig ./tsconfig.json",
    "check:watch": "svelte-kit sync && svelte-check --tsconfig ./tsconfig.json --watch",
    "test:smoke": "playwright test --project=smoke",
    "test:contract": "playwright test --project=contract"
  },
  "devDependencies": {
    "@playwright/test": "^1.44.0",
    "@sveltejs/adapter-node": "^5.0.0",
    "@sveltejs/kit": "^2.0.0",
    "@sveltejs/vite-plugin-svelte": "^3.0.0",
    "playwright": "^1.44.0",
    "svelte": "^4.0.0",
    "svelte-check": "^3.0.0",
    "typescript": "^5.0.0",
    "vite": "^5.0.0"
  }
}
```

- [ ] **Step 2: Install dependencies and Playwright browsers**

```bash
cd apps/user-dashboard && npm install && npx playwright install chromium
```

Expected: `node_modules/@playwright` present, Chromium browser downloaded. No errors.

- [ ] **Step 3: Create `apps/user-dashboard/playwright.config.ts`**

```ts
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
    {
      name: 'contract',
      use: { baseURL: BASE_URLS.dashboard },
      testDir: resolve(__dirname, 'tests/contract'),
    },
  ],
  use: {
    trace: 'on-first-retry',
    screenshot: 'only-on-failure',
  },
  reporter: [['list'], ['html', { open: 'never' }]],
});
```

Note: `BASE_URLS` is imported from `tests/ui-shared/config`, which calls `dotenv.config()` as its first module-level statement. This means `.env.test` is loaded before `BASE_URLS.dashboard` is evaluated. ✓

- [ ] **Step 4: Create test directory placeholders**

Create two empty placeholder files:
- `apps/user-dashboard/tests/smoke/.gitkeep`
- `apps/user-dashboard/tests/contract/.gitkeep`

- [ ] **Step 5: Verify Playwright config loads with zero test files**

```bash
cd apps/user-dashboard && npx playwright test --list
```

Expected output (no errors, zero tests listed):
```
Listing tests:
  [smoke] > (no tests)
  [contract] > (no tests)
```

If you see an import error about `tests/ui-shared/config`, check that the relative path `../../tests/ui-shared/config` resolves correctly from `apps/user-dashboard/`. The file should be at `<repo-root>/tests/ui-shared/config.ts`.

- [ ] **Step 6: Commit**

```bash
git add apps/user-dashboard/package.json apps/user-dashboard/package-lock.json \
  apps/user-dashboard/playwright.config.ts \
  apps/user-dashboard/tests/smoke/.gitkeep \
  apps/user-dashboard/tests/contract/.gitkeep
git commit -m "feat: add Playwright two-suite config for user-dashboard"
```

---

## Task 7: Update user-dashboard CLAUDE.md and .gitignore

**Files:**
- Modify: `apps/user-dashboard/CLAUDE.md`

- [ ] **Step 1: Add Testing section to `apps/user-dashboard/CLAUDE.md`**

Append this section to the end of the file:

```markdown
## Testing

Before marking any UI work done, run all three checks in order:

1. **Type check**: `npm run check` — must pass with zero errors
2. **Smoke tests**: `npm run test:smoke` — requires full local stack (API on 8000, dev server on 5173)
3. **Contract tests**: `npm run test:contract` — no backend needed, CI-safe

Quote the actual terminal output. Do not summarize a passing run.

### Anti-patterns — never do these in test files
- Hardcode `localhost`, port numbers, or base URLs — use `BASE_URLS` from `tests/ui-shared/config.ts`
- Define `beforeEach` login blocks — use the `authedPage` fixture from `tests/ui-shared/fixtures.ts`
- Import `test` or `expect` from `@playwright/test` directly — import from `tests/ui-shared/fixtures.ts`
- Write credential strings — use `TEST_USER` from `tests/ui-shared/config.ts`
- Inline JSON response data in contract tests — add a file to `tests/ui-shared/api-mocks/responses/`

### Shared test utilities (read before writing any test)
- Config: `tests/ui-shared/config.ts` — `BASE_URLS`, `TEST_USER`
- Fixtures: `tests/ui-shared/fixtures.ts` — `test` (smoke), `contractTest` (contract), `expect`
- Auth: `tests/ui-shared/helpers/auth.ts` — `login()`, `logout()`
- API mocks: `tests/ui-shared/api-mocks/handlers.ts` — add entries to `pathToMockFile` for new routes

### Running tests
```bash
# From apps/user-dashboard:
npm run test:smoke      # smoke suite — needs real stack running
npm run test:contract   # contract suite — no backend needed

# Or with Playwright directly:
npx playwright test --project=smoke
npx playwright test --project=contract
npx playwright test --project=contract --reporter=html  # generates report in playwright-report/
```
```

- [ ] **Step 2: Commit**

```bash
git add apps/user-dashboard/CLAUDE.md
git commit -m "docs: add Testing section to user-dashboard CLAUDE.md with SOP and anti-patterns"
```

---

## Task 8: Create ui-dev Superpowers skill

**Files:**
- Create: `~/.claude/skills/ui-dev/SKILL.md`

This file lives outside the repo and is not committed. It is loaded by Claude Code whenever it detects UI work in progress.

- [ ] **Step 1: Create the skill directory**

```bash
mkdir -p ~/.claude/skills/ui-dev
```

- [ ] **Step 2: Create `~/.claude/skills/ui-dev/SKILL.md`**

```markdown
---
name: ui-dev
description: Use when touching .svelte files, files in apps/, or files in tests/ui-shared/. Enforces the UI development SOP for the Tiresias project.
---

# UI Development SOP — Tiresias

## Before writing any UI code

1. Confirm the dev server is responding: `curl -s -o /dev/null -w "%{http_code}" http://localhost:5173` should return `200`
2. Run `npm run check` from the app directory — must exit 0 before proceeding

## Before writing any test file

Grep for anti-patterns in the file you're about to write:
- No `localhost` or port numbers as string literals → use `BASE_URLS` from `tests/ui-shared/config.ts`
- No `import.*from '@playwright/test'` → import from `tests/ui-shared/fixtures.ts`
- No `beforeEach` login flows → use `authedPage` fixture
- No credential strings → use `TEST_USER` from `tests/ui-shared/config.ts`

## After implementation

Run in order, from the app directory:

```bash
npm run check                   # type errors → fix before claiming done
npm run test:contract           # contract suite — no backend needed
npm run test:smoke              # smoke suite — needs full stack
```

## Before claiming done

Quote the FULL terminal output of all three commands above. Do not write "tests passed" — paste the output. If any command fails, fix it before reporting the task complete.

## Hard gates — non-negotiable

- `npm run check` must exit 0
- Contract tests must pass with zero failures
- No URL literals anywhere in test files (outside `config.ts`)
- No credential strings in test files (outside `config.ts`)
```

- [ ] **Step 3: Verify the skill is visible to Claude Code**

```bash
ls ~/.claude/skills/ui-dev/SKILL.md
```

Expected: the file path printed. Claude Code discovers skills in `~/.claude/skills/` automatically on next session start.

---

## Verification Checklist

After all tasks are complete, verify the full infrastructure from a clean state:

- [ ] `tests/ui-shared/node_modules/dotenv` exists
- [ ] `tests/ui-shared/node_modules/@playwright` exists
- [ ] `.env.test.example` is committed and tracked: `git ls-files .env.test.example` returns the path
- [ ] `.env.test` is gitignored: `git check-ignore -v .env.test` returns a match
- [ ] `cd apps/user-dashboard && npx playwright test --list` exits 0 with zero tests
- [ ] `cd apps/user-dashboard && npm run check` exits 0
- [ ] `~/.claude/skills/ui-dev/SKILL.md` exists
