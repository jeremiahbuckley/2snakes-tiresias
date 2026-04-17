# Running Tiresias

This page covers how to start the services, run the tests, and build the container
images. For first-time setup (prerequisites, env vars, migrations) see
[setup.md](setup.md).

## The shape of the stack

Tiresias has four runtime processes and three optional frontends:

| Process | What it is | Port |
|---|---|---|
| `db` | PostgreSQL 16, via `compose.yaml` | 5432 |
| `api-gateway` | FastAPI / Uvicorn. Mounts the auth router today; more to come. | 8000 |
| `scheduler` | APScheduler process driving sync + scoring + leaderboard jobs. | (none — no public port) |
| `user-dashboard` | Private SvelteKit app. Requires `api-gateway`. | Vite default (5173) |
| `public-leaderboard` | Public SvelteKit app. Requires `api-gateway`. | Pick with `--port` |
| `public-profile` | Public SvelteKit app for `/u/:username` and `/share/:token`. | Pick with `--port` |

No Vite port is pinned in any of the three `apps/*/vite.config.js` files, so the first
one you start takes 5173 and the others increment or collide. Pass `--port` explicitly
when running more than one concurrently (examples below).

The API and the scheduler both talk to Postgres. The scheduler imports the connectors
and other services as Python packages (not HTTP calls), so one scheduler process pulls
in every service's code.

## Environment variables

Every process needs at least `DATABASE_URL`. The scheduler additionally needs
`CREDENTIAL_ENCRYPTION_KEY` and all the platform variables. The API needs
`JWT_SECRET_KEY`. The simplest approach for local dev:

```bash
cp .env.example .env.local     # fill in values — see setup.md
set -a; source .env.local; set +a
```

`set -a` exports everything sourced in between, which matches how the services expect to
read env vars.

## Starting things by hand (local dev)

### Postgres

```bash
podman compose up -d db
```

### API gateway

```bash
# PYTHONPATH must cover the services whose routers are mounted by api-gateway.
# Today that's auth-service (and its dep on data-layer); as more routers are
# mounted, extend this list.
export PYTHONPATH=services/data-layer:services/auth-service

uvicorn api_gateway.app:app \
    --app-dir services/api-gateway \
    --reload \
    --port 8000
```

Swagger docs live at http://localhost:8000/docs, the OpenAPI JSON at
http://localhost:8000/openapi.json, and the health check at
http://localhost:8000/health.

### Scheduler

The scheduler is the busy part of the system. Because it invokes every service, its
`PYTHONPATH` needs to cover all of them:

```bash
export PYTHONPATH="\
services/data-layer:\
services/scheduler:\
services/scoring-engine:\
services/badge-service:\
services/notification-service:\
services/connector-kalshi:\
services/connector-polymarket:\
services/connector-manifold:\
services/connector-metaculus"

python -m scheduler.runner
```

On startup you should see:

```
INFO  Scheduler started. Press Ctrl+C to exit.
```

Three jobs register automatically:

| Job | Cadence | What it does |
|---|---|---|
| `sync_markets` | every 15 min | Pulls fills / bets / forecasts from every connected platform for every active user, upserts markets and predictions. |
| `score_resolutions` | every 5 min | Finds newly resolved markets, recomputes affected users' Brier / calibration / BSS, re-evaluates badges, dispatches notifications. |
| `rebuild_leaderboard` | every hour | Full recompute of every user's score from raw predictions, to correct any drift from the incremental path. |

`DATABASE_URL` must be set **before** the `python -m scheduler.runner` command — the
SQLAlchemy async engine is created at module import time.

### Frontends

Each app runs with its own Vite dev server:

```bash
# Dashboard (http://localhost:5173 — Vite default)
cd apps/user-dashboard && npm run dev

# Public leaderboard — explicit port to avoid collision with the dashboard
cd apps/public-leaderboard && npm run dev -- --port 5174

# Public profile
cd apps/public-profile && npm run dev -- --port 5175
```

The dashboard expects the API at `http://localhost:8000`. If you put a reverse proxy in
front, adjust `apps/user-dashboard/src/lib/api.js` accordingly.

## A minimal smoke test

Once the API is up:

```bash
# Create a user
curl -s -X POST http://localhost:8000/auth/register \
    -H 'Content-Type: application/json' \
    -d '{
        "email": "you@example.com",
        "username": "yourhandle",
        "password": "changeme123",
        "display_name": "Your Name"
    }' | python3 -m json.tool

# Log in (gives you a JWT)
TOKEN=$(curl -s -X POST http://localhost:8000/auth/login \
    -H 'Content-Type: application/json' \
    -d '{"email":"you@example.com","password":"changeme123"}' \
    | python3 -c 'import sys,json; print(json.load(sys.stdin)["access_token"])')

# Hit an authenticated route
curl -s http://localhost:8000/auth/me -H "Authorization: Bearer $TOKEN" \
    | python3 -m json.tool
```

A successful `/auth/me` response confirms the database, the auth-service router, and the
JWT signing key are all configured correctly.

## Tests

`pytest.ini` at the repo root turns on `asyncio_mode = auto` and `--import-mode=importlib`.
The root `conftest.py` prepends every service directory to `sys.path`, so most test
suites can be run from the repo root.

```bash
# All unit tests
pytest services/

# One service
pytest services/scoring-engine
pytest services/connector-metaculus

# Integration tests (require a running Postgres; see setup.md)
pytest tests/integration/

# End-to-end tests (require the full stack running)
pytest tests/e2e/
```

Note on Python version: a few scheduler tests import `StrEnum` from stdlib `enum` and so
need Python 3.12. The root `conftest.py` polyfills `StrEnum` for test *collection* on
older interpreters, but at least one test that depends on a 3.12 runtime library feature
will skip or error on 3.10/3.11.

## Building and running containers

Every service has its own `Containerfile` for building a minimal image. The
`compose.yaml` only wires up `db` and `migrate` today; the other services are built and
run by hand (or by whatever production orchestrator you use).

```bash
# Build an image
podman build -f services/scheduler/Containerfile -t tiresias-scheduler services/

# Run migrations as a one-shot container
podman compose run --rm migrate

# Run the scheduler (example — mount the Kalshi key, pass env vars)
podman run -d --name tiresias-scheduler \
    -e DATABASE_URL=postgresql+asyncpg://postgres:postgres@db:5432/tiresias \
    -e CREDENTIAL_ENCRYPTION_KEY=$CREDENTIAL_ENCRYPTION_KEY \
    -e JWT_SECRET_KEY=$JWT_SECRET_KEY \
    -e KALSHI_KEY_ID=$KALSHI_KEY_ID \
    -e KALSHI_PRIVATE_KEY_PATH=/secrets/kalshi.key \
    -v "$KALSHI_PRIVATE_KEY_PATH:/secrets/kalshi.key:ro" \
    --network=tiresias_default \
    tiresias-scheduler
```

A production deployment story (image registry, orchestrator of choice, CI pipeline) is
not yet codified — see [FUTURE_FEATURES.md](../FUTURE_FEATURES.md).

## Troubleshooting

**`asyncpg.exceptions.InvalidCatalogNameError: database "tiresias" does not exist`**
→ Postgres is up but the DB was wiped. Re-run `podman compose run --rm migrate`.

**`cryptography.fernet.InvalidToken` in the scheduler logs**
→ `CREDENTIAL_ENCRYPTION_KEY` doesn't match the key used to encrypt what's in
`linked_accounts.credential_encrypted`. Re-encrypt with the current key via
`python scripts/cred.py encrypt ...`.

**Scheduler starts but syncs nothing**
→ Check that at least one `linked_accounts` row has `is_enabled=true`. The scheduler
only iterates active users (`UserCRUD.list_active()`).

**`sslmode` errors when connecting from the host on macOS**
→ Append `?ssl=disable` to `DATABASE_URL` and use `127.0.0.1` rather than `localhost`.
See the Mac/Podman section in [setup.md](setup.md).

**CORS errors from the browser**
→ The API gateway currently allows all origins (`allow_origins=["*"]`). If you're still
seeing a CORS error, it's almost certainly that the dashboard is pointed at the wrong
API URL.
