# api-gateway

Unified FastAPI application that mounts all service routers under a single HTTP server. The only service exposed to the internet / frontends.

## Tech Stack
- Python 3.12, FastAPI 0.111+, Uvicorn 0.29+

## Key Files
```
api_gateway/
  app.py      # create_app() factory — CORS middleware, mounts routers, /health endpoint
  router.py   # aggregates and re-exports all service routers
```

## Run
```bash
uvicorn api_gateway.app:app --host 0.0.0.0 --port 8000 --reload
```

## Mounted Routers
| Router | Prefix | Source |
|--------|--------|--------|
| auth | `/auth` | `auth_service.api.router` |
| badges | `/badges`, `/users/{id}/badges` | `badge_service.api.router` *(TODO: uncomment in app.py)* |

## Endpoints
```
GET  /health                         # liveness check → {"status": "ok"}
POST /auth/register
POST /auth/login
GET  /auth/me
PUT  /auth/me
POST /auth/link/{platform}
GET  /auth/linked-accounts
DELETE /auth/link/{platform}
GET  /badges
GET  /users/{user_id}/badges
```

## CORS
Currently `allow_origins=["*"]` — restrict to frontend origins before production.

## Adding a New Router
1. Implement a FastAPI `router` in the target service's `api.py`
2. Import and `app.include_router(router)` in `api_gateway/app.py`

## Dependencies
- Imports routers from: `auth_service`, `badge_service`
- Does NOT import connectors, scoring-engine, or scheduler (those run in separate container)

## Env Vars
- `DATABASE_URL` — passed through to data-layer
- `JWT_SECRET` — used by auth-service JWT validation
- `CREDENTIAL_ENCRYPTION_KEY` — used by auth-service linked accounts
