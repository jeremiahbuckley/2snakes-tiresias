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
