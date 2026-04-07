# public-leaderboard

Public-facing leaderboard app — no auth required.

Shows ranked forecasters by Brier Skill Score, with filters by time
period, platform, and domain.

**Stack TBD** — likely a lightweight SSR or static site for SEO/shareability.

## Key pages

- `/` — global leaderboard (all platforms, all time)
- `/?platform=kalshi` — filtered by platform
- `/?domain=politics` — filtered by domain
- `/user/:username` — jumps to that user's public profile
