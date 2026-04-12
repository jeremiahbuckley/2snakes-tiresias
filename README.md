# Tiresias

**Prediction market reputation and badging platform.**

Tiresias aggregates a user's prediction history across multiple markets (Kalshi, Polymarket, Manifold, Metaculus), computes accuracy scores, and issues badges that can be shared publicly — a verifiable track record for forecasters. Scores and badges can be pushed to social platforms (X, Bluesky) and shared anonymously via secret links.

---

## Architecture

```mermaid
graph TD
    subgraph MARKET["📈 Prediction Markets (pull)"]
        K["Kalshi"]
        P["Polymarket"]
        M["Manifold"]
        MC["Metaculus"]
    end

    subgraph SOCIAL["📣 Social Platforms (push)"]
        X["X (Twitter)"]
        BS["Bluesky"]
    end

    subgraph CONN["🔌 Connectors"]
        CK["connector-kalshi"]
        CP["connector-polymarket"]
        CM["connector-manifold"]
        CMC["connector-metaculus"]
    end

    SCH["⏱ scheduler\nevery 15 min · 5 min · 1 hr"]

    subgraph CORE["⚙️ Core Services"]
        SE["📐 scoring-engine\nBrier · Calibration · BSS"]
        BS2["🏅 badge-service\nIssue · Revoke"]
        AS["🔐 auth-service\nJWT · Accounts · Sharing\nNotifications · Profile"]
        NS["🔔 notification-service\nEmail · Push"]
    end

    DL[("🗄 data-layer\nPostgreSQL\nusers · markets · predictions\nscores · linked_accounts\nshare_tokens · notification_prefs")]

    AG["🔀 api-gateway\n/auth · /badges · /users\n/leaderboard · /markets"]

    subgraph APPS["🖥 Frontend Apps"]
        UD["user-dashboard\nSvelteKit · Private · Auth required"]
        PL["public-leaderboard\nSvelteKit · Public · Rankings"]
        PP["public-profile\nSvelteKit · Public · /u/:username · /share/:token"]
    end

    K --> CK
    P --> CP
    M --> CM
    MC --> CMC

    SCH -->|"sync markets"| CK & CP & CM & CMC
    CK & CP & CM & CMC -->|"normalised markets\n& predictions"| DL

    SCH -->|"score resolutions"| SE
    SE -->|"read / write scores"| DL
    SE -->|"scores"| BS2
    BS2 -->|"write badges"| DL
    BS2 -->|"badge events"| NS

    AS -->|"users · linked accounts\nshare tokens · prefs"| DL
    AS -->|"auto-publish scores & badges"| X & BS

    AG --> AS
    AG --> BS2
    AG --> DL

    UD & PL & PP -->|"REST / JSON"| AG
```

---

## Repository Structure

```
tiresias/
├── services/
│   ├── data-layer/          # SQLAlchemy models, Alembic migrations
│   │   └── data/models/     # user, market, prediction, score,
│   │                        # linked_account, share_token, notification_preferences
│   ├── connector-kalshi/    # Kalshi API client, adapter, sync
│   ├── connector-polymarket/# Polymarket CLOB + Gamma client
│   ├── connector-manifold/  # Manifold Markets client
│   ├── connector-metaculus/ # Metaculus client
│   ├── scoring-engine/      # Brier score, calibration, BSS
│   ├── badge-service/       # Badge catalogue, issuer, FastAPI router
│   ├── auth-service/        # JWT, registration, market + social account linking,
│   │                        # share tokens, notification prefs, profile
│   ├── notification-service/# Email/push dispatch, templates
│   ├── scheduler/           # APScheduler background jobs
│   └── api-gateway/         # Unified FastAPI app, mounts all routers
├── apps/
│   ├── user-dashboard/      # Private authenticated frontend (SvelteKit)
│   ├── public-leaderboard/  # Public rankings page (SvelteKit)
│   └── public-profile/      # Shareable profile + anonymous /share/:token (SvelteKit)
└── tests/
    ├── integration/         # Cross-service tests (requires DB)
    └── e2e/                 # Full-stack flow tests (requires running stack)
```

---

## Services

| Service | Role | Key files |
|---|---|---|
| `data-layer` | Shared PostgreSQL models and Alembic migrations | `data/models/`, `alembic/` |
| `connector-*` | Fetch markets & predictions from each platform; normalise to internal format | `client.py`, `adapter.py`, `sync.py` |
| `scoring-engine` | Compute Brier scores, calibration curves, Brier Skill Score | `brier.py`, `calibration.py`, `engine.py` |
| `badge-service` | Define badge criteria; evaluate and issue badges after scoring | `badges.py`, `issuer.py` |
| `auth-service` | Registration, JWT auth, market + social account linking, share tokens, notification prefs, profile | `api.py`, `jwt.py`, `linked_accounts.py` |
| `notification-service` | Send emails/push when markets resolve, badges are earned, or rank changes | `dispatcher.py`, `templates.py` |
| `scheduler` | APScheduler process that drives all background sync and scoring jobs | `jobs.py`, `runner.py` |
| `api-gateway` | Single FastAPI app exposing all service functionality to frontends | `app.py` |

---

## Getting Started

### Prerequisites

- Python 3.12+
- Node.js 20+
- Podman or Docker (for PostgreSQL)

### 1. Create a virtual environment

```bash
python3.12 -m venv .venv
source .venv/bin/activate
pip install fastapi uvicorn sqlalchemy asyncpg alembic \
            bcrypt pyjwt pydantic email-validator greenlet
```

### 2. Start PostgreSQL

```bash
podman compose up -d db
```

### 3. Run migrations

```bash
cd services/data-layer
PYTHONPATH=. \
DATABASE_URL=postgresql+asyncpg://postgres:postgres@localhost:5432/tiresias \
alembic upgrade head
cd ../..
```

### 4. Start the API

```bash
export PYTHONPATH=services/data-layer:services/auth-service
export DATABASE_URL=postgresql+asyncpg://postgres:postgres@localhost:5432/tiresias
export JWT_SECRET_KEY=$(python3 -c "import secrets; print(secrets.token_hex(32))")

uvicorn api_gateway.app:app \
  --app-dir services/api-gateway \
  --reload \
  --port 8000
```

Interactive API docs: **http://localhost:8000/docs**

### 5. Start the user dashboard

```bash
cd apps/user-dashboard
npm install   # first time only
npm run dev
```

Dashboard: **http://localhost:5173**

### 6. Register a user

```bash
curl -s -X POST http://localhost:8000/auth/register \
  -H "Content-Type: application/json" \
  -d '{"email":"you@example.com","username":"yourhandle","password":"changeme123","display_name":"Your Name"}' \
  | python3 -m json.tool
```

---

## Testing

Unit tests live co-located with each service under `services/<name>/tests/`.
Cross-service tests live under `tests/integration/` and `tests/e2e/`.

```bash
# Run unit tests for a single service
cd services/scoring-engine && pytest

# Run all unit tests from repo root (once a root pyproject.toml is added)
pytest services/
```
