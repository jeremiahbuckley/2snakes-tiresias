# user-dashboard

Private authenticated SvelteKit app. The primary user-facing interface for viewing predictions, scores, badges, and managing account settings.

## Tech Stack
- SvelteKit 2.0, Svelte 4, TypeScript 5, Vite 5, Node.js 20+

## Run
```bash
npm run dev      # dev server on http://localhost:5173
npm run build    # production build
npm run preview  # preview production build
```

## Routes
```
/                  # redirect → /dashboard
/login             # login / register forms
/dashboard         # overview: recent predictions, score summary, badge shelf
/predictions       # full prediction history, filterable by platform/status
/stats             # scoring charts: calibration curve, Brier over time, BSS
/settings          # account settings, linked platform credentials, notification prefs
```

## Key Src Files
```
src/
  app.html                    # HTML shell
  lib/                        # shared utilities, API client, stores
  routes/
    +layout.server.js         # session auth check, redirect to /login if unauthenticated
    +layout.svelte            # nav shell
    +page.svelte              # root redirect
    dashboard/                # +page.server.js fetches scores + recent predictions
    login/                    # +page.svelte login/register form
    predictions/              # +page.server.js paginates predictions
    settings/                 # +page.server.js loads linked accounts
    stats/                    # +page.server.js loads scoring data for charts
```

## API Integration
- All data fetched server-side in `+page.server.js` files via internal calls to `api-gateway` (port 8000)
- JWT stored in session cookie; passed as `Authorization: Bearer <token>` header to API
- `API_BASE_URL` env var (default: `http://localhost:8000`)

## Env Vars
- `API_BASE_URL` — URL of api-gateway (set in `.env`)
- `JWT_SECRET` — used server-side for session verification (if using SvelteKit sessions)

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
- Config: `tests/ui-shared/config.ts` — `BASE_URLS`, `TEST_USER`, `assertTestUserConfigured()`
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
