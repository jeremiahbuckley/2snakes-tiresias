# public-profile

Public-facing SvelteKit app for shareable user profiles. Supports both public usernames and anonymous share tokens. Currently a placeholder — not yet implemented.

## Tech Stack
- SvelteKit 2.0, Svelte 4, Vite 5, Node.js 20+

## Status
**Placeholder** — `PLACEHOLDER.md` and `preview.html` present; routes not yet built.

## Run
```bash
npm run dev    # dev server (placeholder page only)
npm run build
```

## Intended Routes
```
/u/[username]       # public profile by username (if user has public profile enabled)
/share/[token]      # anonymous share link (via ShareToken model)
```

## Intended Data Source
- `GET /users/{username}/public` — public profile endpoint on api-gateway
- `GET /share/{token}` — share token endpoint on api-gateway
- No auth required; respects user privacy settings

## Share Token Model
- `ShareToken` in data-layer: `{secret, user_id, public_profile_only}`
- `public_profile_only=true` → shows scores/badges but hides prediction details

## To Implement
1. Build public profile API endpoints in api-gateway
2. Build `+page.server.js` for `/u/[username]` and `/share/[token]`
3. Build profile UI: score summary, badge shelf, prediction history (if permitted)
4. Add OG meta tags for social sharing (preview.html has initial design reference)

## Env Vars
- `API_BASE_URL` — URL of api-gateway
