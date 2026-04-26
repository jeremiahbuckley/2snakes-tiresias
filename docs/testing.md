# Testing

This page covers manual API testing and the automated test suite. For running
the full stack see [running.md](running.md).

---

## Manually testing the API flows

Each connector has a `.http` file with pre-built requests for its platform API.
These are designed to let you walk through the same data path the connector
takes — from raw trade history through to the market metadata that ends up in
the database.

### Prerequisites

- [VS Code REST Client extension](https://marketplace.visualstudio.com/items?itemName=humao.rest-client) (Huachao Mao)
- API credentials set in the root `.env` file (see [setup.md](setup.md))

### One-time setup: create your local file

The tracked `.http` files are clean templates with `YOUR_*` placeholders.
**Never edit them directly for local testing** — use a `.local.http` copy instead.
These are gitignored so your personal values (wallet address, usernames, IDs)
never get committed.

For each connector you want to test, copy its template:

```bash
# Kalshi
cp services/connector-kalshi/rest/kalshi.http \
   services/connector-kalshi/rest/kalshi.local.http

# Polymarket
cp services/connector-polymarket/rest/polymarket.http \
   services/connector-polymarket/rest/polymarket.local.http

# Manifold
cp services/connector-manifold/rest/manifold.http \
   services/connector-manifold/rest/manifold.local.http

# Metaculus
cp services/connector-metaculus/rest/metaculus.http \
   services/connector-metaculus/rest/metaculus.local.http
```

Then open each `.local.http` file and fill in your real values wherever you
see a `YOUR_*` placeholder (wallet address, username, user ID, etc.).

### Running requests

Open a `.local.http` file in VS Code. Each request block has a **Send Request**
link above it — click it to execute and see the response in a split pane.

**Kalshi only:** Kalshi signatures expire after ~30 seconds. Run this in the
terminal immediately before clicking Send Request:

```bash
python services/connector-kalshi/rest/gen_kalshi_auth.py && echo "Ready — send within 30s"
```

Or use the VS Code task **"Kalshi: refresh auth"** (Cmd+Shift+P → Run Task).

### Standard flows

Each `.http` file has a **STANDARD TESTING FLOW** section at the top that walks
through the sequence the connector uses. The short version:

| Connector | Flow summary |
|-----------|-------------|
| **Kalshi** | Fills → note a ticker → GET /markets/{{ticker}} → Settlements |
| **Polymarket** | Trades → note a slug → Closed positions → GET /markets?slug={{slug}} |
| **Manifold** | GET /me (grab userId) → Bets → note a contractId → GET /market/{{contractId}} |
| **Metaculus** | GET /users/me/ (grab forecasterId) → Posts → note a postId → GET /posts/{{postId}}/ |

Follow the numbered steps in the STANDARD TESTING FLOW comment to confirm the
data at each stage matches what the connector's adapter expects.

---

## Automated tests

Run the full test suite from the repo root:

```bash
.venv/bin/pytest
```

Run tests for a single service:

```bash
.venv/bin/pytest services/auth-service/tests/ -v
.venv/bin/pytest services/connector-polymarket/tests/ -v
```

Tests that require a live database are skipped automatically when Postgres is
unavailable (CI and most local runs). To run them locally, start the stack
first (see [running.md](running.md)) and ensure `DATABASE_URL` is set.
