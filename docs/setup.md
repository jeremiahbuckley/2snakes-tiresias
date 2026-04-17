# Setup

This page covers everything needed to go from a fresh `git clone` to a running local
stack. For the steps to actually *run* the services once set up, see
[running.md](running.md).

## Prerequisites

- **Python 3.12 or newer.** The codebase uses `enum.StrEnum`, which is stdlib on 3.12.
  The root `conftest.py` contains a polyfill so test collection still works on 3.10/3.11,
  but the scheduler and runtime code assume 3.12.
- **Node.js 20 or newer** — for the SvelteKit frontends (`apps/`).
- **Podman or Docker.** The local stack runs PostgreSQL 16 in a container via
  `compose.yaml`. Commands below use `podman`; substitute `docker` freely.
- **gitleaks** (optional, recommended) — `brew install gitleaks`. The repo ships a
  pre-commit hook that uses it to block accidental credential commits.

## 1. Python virtual environment

```bash
python3.12 -m venv .venv
source .venv/bin/activate
```

## 2. Install Python dependencies

Each service under `services/` has its own `requirements.txt`. The helper script installs
all of them into the active environment:

```bash
./install-deps.sh
```

That runs `pip install -r requirements.txt` for every service in sorted order. Safe to
re-run; pip will no-op already-satisfied packages.

## 3. Install frontend dependencies

Each of the three SvelteKit apps has its own `package.json`. Install as needed:

```bash
cd apps/user-dashboard    && npm install && cd ../..
cd apps/public-leaderboard && npm install && cd ../..
cd apps/public-profile    && npm install && cd ../..
```

You only need to install the apps you intend to run.

## 4. Environment variables

Copy the template and fill in the blanks:

```bash
cp .env.example .env.local
```

`.env.local` is gitignored. Never commit it. Distribute real values out-of-band
(encrypted email, 1Password, etc.).

The full list of variables lives in `.env.example` with inline documentation. A
summary of what each one does:

| Variable | Purpose |
|---|---|
| `DATABASE_URL` | Async Postgres connection string. Must use the `postgresql+asyncpg://` scheme, not plain `postgresql://`. |
| `CREDENTIAL_ENCRYPTION_KEY` | Fernet key used by the scheduler and auth-service to encrypt platform credentials stored in `linked_accounts`. Generate with `python scripts/cred.py genkey`. |
| `JWT_SECRET_KEY` | HMAC key used by auth-service to sign access tokens and unsubscribe tokens. Generate with `python -c "import secrets; print(secrets.token_hex(32))"`. |
| `KALSHI_KEY_ID`, `KALSHI_PRIVATE_KEY_PATH` | Kalshi uses RSA-PSS request signing. Create an API key at kalshi.com/account/profile, save the `.key` file locally, and point `KALSHI_PRIVATE_KEY_PATH` at it. |
| `POLYMARKET_WALLET_ADDRESS` | Polygon proxy wallet address for the user whose positions you want to sync. Gamma and Data APIs are fully public — no API key needed. |
| `MANIFOLD_API_KEY` | Bearer token from Manifold. |
| `METACULUS_TOKEN` | Metaculus token. Public GETs work without it, but rate limits are much higher with one. |

The same `CREDENTIAL_ENCRYPTION_KEY` must be set for every process that reads or writes
stored credentials (scheduler, auth-service, CLI tools). If it differs, the scheduler
will fail to decrypt keys and sync will silently produce no data.

## 5. Start PostgreSQL

```bash
podman compose up -d db
```

`compose.yaml` bind-mounts the Postgres data directory to `./data/postgres` so the
database survives container restarts. To wipe it completely:

```bash
podman compose down
rm -rf data/postgres
```

## 6. Run migrations

```bash
podman compose run --rm migrate
```

This builds the `services/data-layer` container and runs `alembic upgrade head` inside
it. The schema is defined by migrations `0001_initial_schema` through
`0004_email_deliveries` under `services/data-layer/alembic/versions/`.

To run Alembic directly from the host (useful when authoring a new migration):

```bash
cd services/data-layer
PYTHONPATH=. DATABASE_URL=postgresql+asyncpg://postgres:postgres@127.0.0.1:5432/tiresias \
  alembic upgrade head
cd ../..
```

## 7. (Optional) Enable the pre-commit hook

`.gitleaks.toml` in the repo root extends the default gitleaks ruleset with
project-specific allowlists. A pre-commit hook at `.git/hooks/pre-commit` runs it on
staged diffs before every commit. If you want the protection, install `gitleaks` and make
sure the hook is executable:

```bash
brew install gitleaks
chmod +x .git/hooks/pre-commit   # if it's not already
```

## 8. Link a platform account (optional, needed for sync)

The scheduler only syncs for users who have rows in the `linked_accounts` table with
`is_enabled=true` and a Fernet-encrypted credential. Easiest way to seed one for local
testing:

```bash
# Encrypt your raw Metaculus token (or Manifold key, etc.)
python scripts/cred.py encrypt "your-raw-token"
# → prints an opaque base64 blob

# Then patch it into the DB row for your local user
podman exec -it <postgres-container-id> psql -U postgres -d tiresias -c "
UPDATE linked_accounts
SET is_enabled=true,
    is_verified=true,
    external_identifier='<your-metaculus-integer-id>',
    credential_encrypted='<encrypted-output-from-above>'
WHERE user_id='<your-user-uuid>' AND platform='metaculus';"
```

There is also `scripts/test_metaculus_live.py` for end-to-end smoke testing once the
row is set up.

Per-platform linking via the UI flows through `PUT /auth/me/linked-accounts/{platform}`
in the auth-service, but that endpoint currently stores credentials without Fernet
encryption (see the `TODO` in `services/auth-service/auth_service/api.py`). Until that
gap is closed, stored credentials should be inserted via `scripts/cred.py` as above.

## Mac / Podman gotchas

If you're running Podman on macOS (via `gvproxy`), two small traps are worth knowing:

- **Use `127.0.0.1`, not `localhost`.** `localhost` resolves to `::1` on macOS and the
  container only listens on IPv4 through gvproxy.
- **Disable SSL on the async driver.** asyncpg defaults to attempting SSL; add
  `?ssl=disable` to the URL:
  `postgresql+asyncpg://postgres:postgres@127.0.0.1:5432/tiresias?ssl=disable`.

Both only matter when running Python code on the host against a containerised Postgres.
Inside a container talking to the `db` service by hostname, neither applies.

## Verifying the setup

```bash
# Can the DB be reached?
PGPASSWORD=postgres psql -h 127.0.0.1 -U postgres -d tiresias -c 'SELECT 1;'

# Does the schema look right?
PGPASSWORD=postgres psql -h 127.0.0.1 -U postgres -d tiresias -c '\dt'
# Should list: users, markets, predictions, user_scores, linked_accounts,
#              share_tokens, notification_preferences, email_deliveries,
#              alembic_version
```

If that works, move on to [running.md](running.md).
