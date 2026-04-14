# public-leaderboard

Public-facing SvelteKit app displaying ranked user scores. No authentication required. Currently a placeholder — not yet implemented.

## Tech Stack
- SvelteKit 2.0, Svelte 4, Vite 5, Node.js 20+

## Status
**Placeholder** — `PLACEHOLDER.md` present; routes not yet built.

## Run
```bash
npm run dev    # dev server (placeholder page only)
npm run build
```

## Intended Routes
```
/              # ranked leaderboard table (all users, sortable by brier/bss/calibration)
/[username]    # redirect → public-profile app
```

## Intended Data Source
- Fetch pre-computed leaderboard snapshot from api-gateway
- Snapshot rebuilt hourly by `scheduler` job `rebuild_leaderboard`
- No auth required — all data is public

## To Implement
1. Build leaderboard API endpoint in api-gateway (GET `/leaderboard`)
2. Build `+page.server.js` to fetch leaderboard data
3. Build `+page.svelte` with sortable table component
4. Wire up pagination / infinite scroll

## Env Vars
- `API_BASE_URL` — URL of api-gateway
