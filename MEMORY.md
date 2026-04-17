# Tiresias — Session Memory

Read this at the start of every Cowork session to pick up where we left off.

---

## What this project is

**Tiresias** — a prediction market reputation and badging platform. Aggregates a user's prediction history across Kalshi, Polymarket, Manifold, and Metaculus; computes Brier scores and calibration; issues badges; publishes to X/Bluesky. Three SvelteKit frontends (user dashboard, public leaderboard, public profile).

Full architecture is in `README.md`.

---

## Current state (as of 2026-04-14)

### What's built and working
- All data-layer models, migrations, CRUD (migrations 0001–0003)
- All four connector services (Kalshi, Polymarket, Manifold, Metaculus) — clients, adapters, sync functions
- Scoring engine (Brier, calibration, BSS)
- Badge service (catalogue, issuer, diff)
- Auth service (JWT, registration, linked accounts)
- Notification service (dispatcher + templates — **stubs only**, handlers not implemented)
- API gateway (routes wired up)
- User dashboard SvelteKit app
- **Scheduler — just fully implemented this session** (see below)

### What was just completed (this session)
The scheduler (`services/scheduler/`) was a skeleton with four `NotImplementedError` stubs. We implemented everything:

**Data-layer additions** (required by scheduler):
- `Market` model: added `source` + `external_id` columns, partial unique index `uq_market_source_external`
- `Prediction` model: added `source` + `external_id` columns
- `UserScore` model: added `badge_ids JSONB` column
- `MarketCRUD`: added `get_by_external`, `upsert_from_sync`, `list_resolved_with_unscored_predictions`
- `PredictionCRUD`: added `upsert_from_sync`
- `UserCRUD`: added `list_active`
- Migration `0003_sync_external_ids.py` covers all of the above

**New scheduler files**:
- `scheduler/credentials.py` — Fernet decryption for stored API keys (`CREDENTIAL_ENCRYPTION_KEY` env var)
- `scheduler/sync.py` — per-platform sync helpers: `sync_one_user()` + `_sync_kalshi/manifold/metaculus/polymarket()`
- `scheduler/jobs.py` — all 4 jobs fully implemented (see below)
- `scheduler/tests/test_jobs.py` — 20 test cases
- `requirements.txt` updated (added sqlalchemy, asyncpg, cryptography)
- `Containerfile` updated (now copies data-layer, scoring-engine, badge-service, notification-service)

**The 4 jobs:**
1. `sync_user_predictions(user_id)` — on-demand, syncs one user across all linked platforms
2. `sync_all_markets()` — every 15 min, calls sync_one_user for all active users
3. `detect_and_score_resolutions()` — every 5 min, scores resolved predictions, updates UserScore, evaluates badges, dispatches notifications
4. `rebuild_leaderboard()` — every 1 hr, full recompute of user_scores from raw predictions

### What's NOT done yet
- Notification service handlers (`_handle_market_resolved`, `_handle_badge_earned`, `_handle_rank_change` all raise `NotImplementedError`) — scheduler calls dispatch() but silently swallows these errors for now
- Auth service credential verification stubs (`verify_kalshi_credential` etc. all raise `NotImplementedError`)
- Kalshi per-user credentials — currently uses env-var-based RSA key (single key for all users); per-user Kalshi support requires passing PEM bytes to KalshiClient constructor
- Integration / E2E tests (`tests/integration/`, `tests/e2e/` directories exist but are empty)
- Public leaderboard and public profile SvelteKit apps (may not exist yet)
- Social publishing (push to X / Bluesky) — not designed yet; intentionally deferred

### Metaculus sync — completed 2026-04-15

The Metaculus connector is now fully covered and pagination-correct:

**`connector_metaculus/client.py`** — `get_user_posts` upgraded from single-page to full auto-pagination. Follows `next` URLs until exhausted; uses `limit=100` per page. Adds `logging` import and debug log lines per page.

**`connector_metaculus/tests/test_sync.py`** (NEW — 17 tests, all passing):
- `TestSyncUserForecasts` (8 tests) — binary-only filter, last-forecast selection, empty results, no-forecast edge case, source/external_id shape, user_id forwarding
- `TestSyncMarket` (5 tests) — normalised dict shape, resolved/open, tags, timestamps
- `TestPagination` (4 tests) — `sync_user_forecasts` sees all pages; `get_user_posts` follows `next` links (1 page = 1 request, 2 pages = 2 requests, empty = 0 results)
- All 34 connector-metaculus tests pass (17 adapter + 17 sync)

**`scheduler/tests/test_jobs.py`** — `TestSyncMetaculus` class extended with 9 new tests:
- `test_skips_when_no_external_identifier` — empty string → 0
- `test_happy_path_upserts_markets_and_predictions` — full path: posts → markets → predictions → count=1
- `test_uses_per_user_token_not_env_var` — verifies decrypted token is passed to MetaculusClient constructor
- `test_non_binary_posts_are_skipped` — numeric post → 0 markets, 0 predictions
- `test_market_fetch_failure_skips_prediction_but_continues` — one bad market → skipped, others continue
- `test_prediction_with_none_probability_is_skipped` — empty my_forecasts → upsert_from_sync returns None → count=0
- `test_multiple_posts_all_succeed` — 3 posts → count=3
- Note: scheduler tests require Python 3.12+ (`StrEnum`) and can't run in the Python 3.10 sandbox; they pass locally.

**`scripts/test_metaculus_live.py`** (NEW) — end-to-end smoke test script. Run against a live DB to confirm predictions land:
- Phase 1: API connectivity check via `/api/users/me/` and `get_user_posts`
- Phase 2: runs `_sync_metaculus` and commits
- Phase 3: asserts markets exist with titles, resolved markets have outcomes, predictions exist with non-None probabilities
- Supports `--user-id <uuid>` and `--dry-run` flags

---

## Known issues / active debugging

### Scheduler end-to-end verified ✓
DB connectivity confirmed and scheduler runs successfully. Key findings:
- DB URL must use `postgresql+asyncpg://` (not `postgresql://`) for async engine
- Port is `5432`, host is `127.0.0.1` (not `localhost`) on Mac with Podman/gvproxy
- `DATABASE_URL` must be set **before** importing `scheduler.jobs` (engine is created at module load time)
- The Python REPL requires pressing **Enter twice** to execute a multi-line block

### Linked account setup for local testing
User `a80f20a1-f307-49e6-8676-34e5aa79e59c` (jeremiahbuckley) has a Metaculus linked account.
Needs `is_enabled=true`, `is_verified=true`, and correct integer Metaculus user ID in `external_identifier`.
Credential must be Fernet-encrypted using `CREDENTIAL_ENCRYPTION_KEY` — use `scripts/cred.py` for this.

```bash
# Encrypt a token
python scripts/cred.py encrypt "your-raw-token"

# Then update the DB row
podman exec -it <postgres-container> psql -U postgres -d tiresias -c "
UPDATE linked_accounts
SET is_enabled=true, is_verified=true,
    external_identifier='<metaculus-integer-id>',
    credential_encrypted='<encrypted-output>'
WHERE user_id='a80f20a1-f307-49e6-8676-34e5aa79e59c' AND platform='metaculus';"
```

---

## Key architectural decisions made

- One prediction per (user_id, market_id) — manually-entered predictions are never overwritten by syncs
- External synced predictions use the most recent bet's probability (last-write-wins per market)
- Badge state stored as JSONB on UserScore (not a separate table) for V1 simplicity
- Notification errors are non-fatal in the scheduler — `NotImplementedError` from stub handlers is silently swallowed
- Scheduler imports other services as Python packages (not HTTP) — all bundled in one container
- Kalshi uses env-var RSA key for V1 (per-user Kalshi keys are a future improvement)
- `CREDENTIAL_ENCRYPTION_KEY` env var holds the Fernet key for decrypting stored API keys

---

## How to run things locally

```bash
# Start DB
podman compose up -d db   # from repo root

# Set up Python path (from services/)
export PYTHONPATH="$PWD/scheduler:$PWD/data-layer:$PWD/scoring-engine:$PWD/badge-service:$PWD/notification-service:$PWD/connector-kalshi:$PWD/connector-manifold:$PWD/connector-metaculus:$PWD/connector-polymarket"

# Run migrations
cd data-layer
DATABASE_URL="postgresql+asyncpg://postgres:postgres@127.0.0.1:5432/tiresias?ssl=disable" \
PYTHONPATH=. alembic upgrade head
cd ..

# Start scheduler
DATABASE_URL="postgresql+asyncpg://postgres:postgres@127.0.0.1:5432/tiresias?ssl=disable" \
python -m scheduler.runner

# Start API
export DATABASE_URL="postgresql+asyncpg://postgres:postgres@127.0.0.1:5432/tiresias?ssl=disable"
export JWT_SECRET_KEY=$(python3 -c "import secrets; print(secrets.token_hex(32))")
uvicorn api_gateway.app:app --app-dir api-gateway --reload --port 8000
```

Note: use `127.0.0.1` not `localhost`, and `?ssl=disable` — required due to Podman/gvproxy on Mac.

---

## Security / secrets tooling added

- `scripts/cred.py` — encrypt/decrypt credentials for the DB using the Fernet key
- `.env.example` — template showing all required env vars (safe to commit, no real values)
- `.gitleaks.toml` — gitleaks config extending the default ruleset with project-specific allowlists
- `.git/hooks/pre-commit` — blocks commits containing detected secrets (requires `brew install gitleaks`)

**QA secrets workflow:**
1. Generate a key once: `python scripts/cred.py genkey`
2. Share the key out-of-band (encrypted email, 1Password, etc.)
3. Each dev puts it in `.env.local` (gitignored)
4. Encrypt tokens before storing in DB: `python scripts/cred.py encrypt "raw-token"`

---

## What to work on next (suggested order)

1. **Run Metaculus live smoke test** — fix linked_account row (is_enabled=true, correct integer Metaculus user ID, Fernet-encrypted token), then run `python scripts/test_metaculus_live.py --user-id <uuid>` to verify predictions land in DB end-to-end
2. **Implement notification service handlers** (email via Resend/SendGrid/Postmark)
3. **Implement auth service credential verifiers** (`verify_kalshi_credential` etc. all raise `NotImplementedError`)
4. **Integration tests** — wire up `tests/integration/` with a real test DB
5. **Public leaderboard + public profile** frontend apps

---

## Kalshi API Migration (openapi-20260415.yaml) — DONE 2026-04-15

`client.py` and `adapter.py` updated and all 26 tests passing. Changes applied:
- Base URL: `trading-api.kalshi.com` → `api.elections.kalshi.com`
- Fills: `count`/`yes_price` (int cents) → `count_fp`/`yes_price_dollars` (fixed-point strings); `fill_id` now primary ID over `trade_id`; old fields kept as fallbacks
- Settlements: `updated_time` → `settled_time`; `market_result` now handles `scalar` and `void` in addition to `yes`/`no`
- Markets: `expiration_time` → `latest_expiration_time`; `title` falls back to `yes_sub_title`/`no_sub_title`
- Pagination cursor now available on all three list endpoints (TODOs still open in client.py)

---

## Manifold — Multi-Choice Market Bug (V2)

`services/connector-manifold/connector_manifold/sync.py` has a latent bug for multi-choice markets. No changes needed for V1 (binary only), but document here for V2.

**The problem:** `sync_market(market_external_id)` passes the bet's `contractId` to `GET /v0/market/{id}`. For binary markets `contractId == marketId` so this works. For multi-choice markets, a bet's `contractId` is an answer-level contract ID, not the top-level market ID — the lookup 404s.

**Root cause:** Manifold has a one-to-many relationship between markets and contracts (each answer in a multi-choice market is its own contract). Bets reference the answer-level `contractId`. There is no `GET /v0/contract/{id}` endpoint to resolve an answer contract back to its parent market.

**V1 status:** Not a problem — `normalise_bet` only handles `"YES"`/`"NO"` outcomes and the scoring engine uses binary Brier scores. Multi-choice bets would produce wrong probability values regardless, so the full fix belongs in V2.

**V2 fix approach:** When `get_market(contractId)` returns a 404, fall back to `GET /v0/markets` (paginated bulk scan), build a map of `answerId → parentMarket`, and resolve from there. Alternatively, `GET /v0/get-user-contract-metrics-with-contracts` returns positions and full market objects together in one call — consider replacing the bet+market sync pattern with this endpoint for Manifold.

---

## REST Test Files (created 2026-04-15)

- `services/connector-kalshi/rest/kalshi.http` — VS Code REST Client requests for all 4 Kalshi endpoints
- `services/connector-kalshi/rest/gen_kalshi_auth.py` — generates RSA-PSS-SHA256 auth headers into `rest/.env`; run before each test session from `services/connector-kalshi/`
- `services/connector-kalshi/rest/http-client.env.json` — production/demo environment switcher
- `services/connector-polymarket/rest/polymarket.http` — VS Code REST Client requests for Polymarket (no auth needed)

Kalshi test workflow: fill `KALSHI_KEY_ID` and `KALSHI_PRIVATE_KEY_PATH` in root `.env`, then `python rest/gen_kalshi_auth.py`

Polymarket test workflow: open `polymarket.http`, click Send Request. Wallet: `0xFf087b904c694BdC4F2710940E4BeEDDAD7Efccc`
