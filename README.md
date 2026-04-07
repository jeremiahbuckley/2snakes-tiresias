# Tiresias

**Prediction market reputation and badging platform.**

Tiresias aggregates a user's prediction history across multiple markets (Kalshi, Polymarket, Manifold, Metaculus), computes accuracy scores, and issues badges that can be shared publicly — a verifiable track record for forecasters.

---

## Architecture

```mermaid
graph TD
    subgraph EXT["🌐 External Platforms"]
        K["Kalshi"]
        P["Polymarket"]
        M["Manifold"]
        MC["Metaculus"]
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
        BS["🏅 badge-service\nIssue · Revoke"]
        AS["🔐 auth-service\nJWT · Account linking"]
        NS["🔔 notification-service\nEmail · Push"]
    end

    DL[("🗄 data-layer\nPostgreSQL")]

    AG["🔀 api-gateway\n/auth · /badges · /users\n/leaderboard · /markets"]

    subgraph APPS["🖥 Frontend Apps"]
        UD["user-dashboard\nPrivate · Auth required"]
        PL["public-leaderboard\nPublic · Rankings"]
        PP["public-profile\nPublic · Shareable"]
    end

    K --> CK
    P --> CP
    M --> CM
    MC --> CMC

    SCH -->|"sync markets"| CK & CP & CM & CMC
    CK & CP & CM & CMC -->|"normalised markets\n& predictions"| DL

    SCH -->|"score resolutions"| SE
    SE -->|"read / write scores"| DL
    SE -->|"scores"| BS
    BS -->|"write badges"| DL
    BS -->|"badge events"| NS

    AS -->|"users & linked accounts"| DL

    AG --> AS
    AG --> BS
    AG --> DL

    UD & PL & PP -->|"REST / JSON"| AG
```

---

## Repository Structure

```
tiresias/
├── services/
│   ├── data-layer/          # SQLAlchemy models, CRUD, Alembic migrations
│   ├── connector-kalshi/    # Kalshi API client, adapter, sync
│   ├── connector-polymarket/# Polymarket CLOB + Gamma client
│   ├── connector-manifold/  # Manifold Markets client
│   ├── connector-metaculus/ # Metaculus client
│   ├── scoring-engine/      # Brier score, calibration, BSS
│   ├── badge-service/       # Badge catalogue, issuer, FastAPI router
│   ├── auth-service/        # JWT, account linking per platform
│   ├── notification-service/# Email/push dispatch, templates
│   ├── scheduler/           # APScheduler background jobs
│   └── api-gateway/         # Unified FastAPI app, mounts all routers
├── apps/
│   ├── user-dashboard/      # Private authenticated frontend (TBD stack)
│   ├── public-leaderboard/  # Public rankings page
│   └── public-profile/      # Shareable per-user profile + OG card
└── tests/
    ├── integration/         # Cross-service tests (requires DB)
    └── e2e/                 # Full-stack flow tests (requires running stack)
```

---

## Services

| Service | Role | Key files |
|---|---|---|
| `data-layer` | Shared PostgreSQL models, CRUD helpers, Alembic migrations | `data/models/`, `data/crud/`, `alembic/` |
| `connector-*` | Fetch markets & predictions from each platform; normalise to internal format | `client.py`, `adapter.py`, `sync.py` |
| `scoring-engine` | Compute Brier scores, calibration curves, Brier Skill Score | `brier.py`, `calibration.py`, `engine.py` |
| `badge-service` | Define badge criteria; evaluate and issue badges after scoring | `badges.py`, `issuer.py` |
| `auth-service` | User registration, JWT tokens, linking external platform accounts | `jwt.py`, `linked_accounts.py` |
| `notification-service` | Send emails/push when markets resolve, badges are earned, or rank changes | `dispatcher.py`, `templates.py` |
| `scheduler` | APScheduler process that drives all background sync and scoring jobs | `jobs.py`, `runner.py` |
| `api-gateway` | Single FastAPI app exposing all service functionality to frontends | `app.py`, `router.py` |

---

## Getting Started

Each service has its own `requirements.txt`. To work on a service locally:

```bash
cd services/scoring-engine
pip install -r requirements.txt
pytest tests/
```

The data layer requires a running PostgreSQL instance:

```bash
# Set your connection string
export DATABASE_URL=postgresql+asyncpg://postgres:postgres@localhost:5432/tiresias

# Run migrations
cd services/data-layer
alembic upgrade head
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
