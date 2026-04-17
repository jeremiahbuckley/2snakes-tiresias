# Tiresias

**Prediction market reputation and badging platform.**

Tiresias aggregates a user's prediction history across Kalshi, Polymarket, Manifold, and
Metaculus, computes accuracy scores (Brier, calibration, Brier Skill Score), issues
badges, and lets forecasters share a verifiable track record publicly or via anonymous
links. A private SvelteKit dashboard gives the forecaster their personal view; a public
leaderboard and shareable profile pages surface the results to everyone else.

---

## Quick start

Assumes Python 3.12+, Node.js 20+, and Podman (or Docker) are already installed.

```bash
# From the repo root, after `git clone`:
python3.12 -m venv .venv && source .venv/bin/activate
./install-deps.sh                       # installs Python deps for every service

cp .env.example .env.local              # then fill in the blanks — see docs/setup.md
export $(grep -v '^#' .env.local | xargs)

podman compose up -d db                 # start Postgres
podman compose run --rm migrate         # apply schema migrations

# Run the API, the scheduler, and the dashboard in three terminals:
uvicorn api_gateway.app:app --app-dir services/api-gateway --reload --port 8000
python -m scheduler.runner
cd apps/user-dashboard && npm install && npm run dev
```

API docs: http://localhost:8000/docs · Dashboard: http://localhost:5173

For anything this snippet glosses over (how to generate keys, how to link a platform
account, how to run the public leaderboard, the Mac/Podman gotchas) see the full docs
below.

---

## Documentation

| Topic | Where |
|---|---|
| Full post-clone setup | [docs/setup.md](docs/setup.md) |
| Running the app (local, containerised, tests) | [docs/running.md](docs/running.md) |
| Tech stack, repo layout, system diagram | [docs/architecture.md](docs/architecture.md) |
| User personas | [docs/personas.md](docs/personas.md) |
| Workflows per persona | [docs/workflows.md](docs/workflows.md) |
| Deferred work | [FUTURE_FEATURES.md](FUTURE_FEATURES.md) |
| Session notes for Cowork / Claude Code | [MEMORY.md](MEMORY.md) |

The canonical system diagram lives in [docs/architecture.md](docs/architecture.md).
