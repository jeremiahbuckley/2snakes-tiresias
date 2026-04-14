# scheduler

Background job orchestrator. Runs all periodic sync, scoring, badge-issuance, and leaderboard jobs using APScheduler. Imports all other services as Python packages (no HTTP calls between them).

## Tech Stack
- Python 3.12, APScheduler 3.10 (AsyncIOScheduler), sqlalchemy (via data-layer)

## Key Files
```
scheduler/
  runner.py        # build_scheduler() + main() — registers jobs, starts AsyncIOScheduler event loop
  jobs.py          # 3 async job functions imported by runner
  sync.py          # _sync_platform(user_id, platform, db) — per-platform sync helper, dispatches to connectors
  credentials.py   # get_decrypted_credentials(user_id, db) — Fernet decrypt of LinkedAccount fields
```

## Jobs & Schedule
| Job | Interval | Function |
|-----|----------|----------|
| `sync_markets` | every 15 min | `sync_all_markets` — iterates all users with linked accounts, calls each connector |
| `score_resolutions` | every 5 min | `detect_and_score_resolutions` — finds newly resolved markets, scores affected users |
| `rebuild_leaderboard` | every 1 hour | `rebuild_leaderboard` — recomputes leaderboard snapshot (details in jobs.py) |

## Run
```bash
python -m scheduler.runner
```
Container entrypoint also runs this command (see Containerfile).

## Architecture Note
The scheduler container bundles **all services** — connectors, scoring-engine, badge-service, notification-service are all installed into the same container image and imported directly. This avoids inter-service HTTP overhead for batch jobs.

## Dependency Chain (per sync cycle)
```
sync_all_markets
  → credentials.py (decrypt LinkedAccount)
  → sync.py → connector_{platform}.sync.sync_user_predictions()
      → data-layer crud upserts

detect_and_score_resolutions
  → scoring_engine.engine.score_predictions()
      → badge_service.issuer.evaluate_and_issue_badges()
          → notification_service.dispatcher.dispatch("badge_earned")
```

## Env Vars
- `DATABASE_URL` — PostgreSQL connection string (add `?ssl=disable` for Podman)
- `CREDENTIAL_ENCRYPTION_KEY` — Fernet key for decrypting stored API credentials
- `JWT_SECRET` — needed if any job triggers authenticated API calls
