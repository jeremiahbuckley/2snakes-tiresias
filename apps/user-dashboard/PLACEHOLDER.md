# user-dashboard

Private authenticated app — shows a user their full prediction history,
per-platform breakdowns, calibration charts, badge collection, and
account linking UI.

**Stack TBD** — likely React + Vite or Next.js, consuming the api-gateway.

## Key pages

- `/dashboard` — overview: score summary, badges, recent activity
- `/predictions` — full prediction history with filters
- `/stats` — calibration curve, Brier score over time, domain breakdown
- `/settings` — account linking (Kalshi, Polymarket, Manifold, Metaculus),
  notification preferences, profile display name
