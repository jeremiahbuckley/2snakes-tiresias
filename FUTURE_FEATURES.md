# Future Features

Tracked ideas and deferred work for Tiresias. Items here are intentionally out of scope for v1 but should be considered before or shortly after launch.

---

## Connectors

### Tag-based whitelist / blacklist per platform per user
A user may only want to report on a specific slice of their prediction history. For example: show NBA bets on Polymarket but exclude International Relations bets. The platform account linking record (in auth-service) should allow a per-user, per-platform configuration of allowed and blocked tags. Sync and scoring would then filter bets against these lists at ingest time.

Things to think through:
- Tag vocabularies differ across platforms (Kalshi uses series/event tags, Polymarket uses Gamma category tags, Manifold uses free-form tags, Metaculus uses category slugs). Two options: normalise tags into a common internal taxonomy (better for cross-platform topic reporting, e.g. "all my geopolitics bets across every platform") or store platform-specific filter configs per user (simpler to build first). Decide before implementation.
- Whitelist and blacklist should be independently optional (whitelist-only = only these; blacklist-only = everything except these; both = whitelist applied first, then blacklist).
- Needs a UI surface in the user-dashboard for editing these filters.

### API rate-limit strategy for Kalshi
Kalshi Basic tier allows 20 reads/second. For v1 with a small number of users, a full sync (fills + settlements + one market fetch per unique ticker) stays well within this limit. As user count grows and syncs begin running in parallel, a shared rate-limiter will be needed to avoid 429s.

Likely shape: a thin `RateLimiter` (or `PullStrategy`) class wrapping the Kalshi client that enforces a configurable request-per-second ceiling using a token bucket or sliding window. The scheduler's sync jobs would acquire a token before each request. Advanced tier (30 req/s) is available via a Kalshi typeform application if Basic becomes a bottleneck before a custom limiter is worth building.

Rate limit tiers for reference:
- Basic: 20 reads / 10 writes per second (default on signup)
- Advanced: 30 / 30 (application required)
- Premier: 100 / 100 (3.75% of exchange volume/month)
- Prime: 400 / 400 (7.5% of exchange volume/month)

Write-limit applies only to order creation/cancellation/amendment endpoints — not relevant for v1.

### Pagination
All four connector clients currently fetch only the first page of results. Cursor-based pagination (Kalshi, Polymarket) and offset-based pagination (Metaculus) need to be implemented before any user with a meaningful prediction history can be fully synced.

### Non-binary market support
Manifold (FREE_RESPONSE, MULTIPLE_CHOICE, NUMERIC) and Polymarket (multi-outcome) support non-binary markets. The current adapters skip or partially handle these. Scoring for non-binary markets also requires a different formulation (e.g. ranked probability score).

### Kalshi WebSocket client
The REST connector handles point-in-time syncs. A WebSocket client (`ws_client.py`) could subscribe to `market_lifecycle_v2` and `ticker` channels to get push notifications on resolutions and price changes, reducing sync latency and API load. Low priority until sync cadence is proven insufficient.

---

## User Dashboard

### Refresh data button
The user dashboard should expose a "Refresh data" button that triggers the scheduler's on-demand `sync_user_predictions(user_id)` job for the signed-in user, so they can pull their latest predictions without waiting for the next scheduled `sync_all_markets` tick (currently every 15 min).

Things to think through:
- Surface: add a button near the last-synced timestamp on the dashboard header. Show a spinner + "Syncing…" state while the job runs and a toast (success/error) when it returns.
- API: either a new `POST /auth/me/sync` that enqueues the scheduler job, or expose scheduler's on-demand job via a thin API endpoint (e.g. `POST /scheduler/sync-user/{user_id}` gated to the authenticated user only). The scheduler already implements `sync_user_predictions` — this is mostly a plumbing task.
- Rate-limit client-side (disable button for ~30s after click) and server-side (reject if the user has triggered a sync within the last N seconds) to avoid hammering the upstream platforms. This also ties into the Kalshi rate-limit work tracked above.
- Consider whether a sync should be fire-and-forget (return 202 immediately, UI polls for last-synced timestamp) or awaited (return 200 once the sync finishes). Fire-and-forget is friendlier if any single platform is slow.
- Errors per-platform should be surfaced gracefully — if Manifold fails but Kalshi succeeds, the UI should show partial success rather than "sync failed".

---

## Go-to-Market

### Per-user platform opt-in / opt-out
Users should be able to choose which prediction market platforms they connect to Tiresias. This is both a UX preference and a legal necessity: Polymarket is restricted or blocked in many US states, and Kalshi has geographic restrictions as well. A user in a restricted region should never be shown a Polymarket onboarding flow, and a user who simply doesn't use a given platform shouldn't have to connect it.

Things to think through:
- The auth-service linked accounts model already implies opt-in per platform (you only link what you use), but this needs to be surfaced clearly in the onboarding UI.
- Geographic restrictions should ideally be checked at signup/linking time and used to hide unavailable platforms entirely rather than showing them grayed out. Polymarket publishes a geoblock list; Kalshi restricts certain markets by state.
- Consider whether platform availability should be stored server-side (so it can be updated without a client deploy) or derived at runtime from the user's region.
- For users who later move into or out of a restricted region, there should be a path to link/unlink platforms without losing historical data.

---

## Auth & Account Linking

### Credential encryption at rest
External platform credentials (Kalshi key path, Manifold API key, Metaculus token, Polymarket wallet address) are currently stored as plaintext in the linked accounts table. These should be encrypted at rest using a server-side key (e.g. via Fernet or AWS KMS).

### Polymarket wallet verification
Polymarket auth is wallet-based rather than API-key-based. The auth-service needs to implement EIP-712 signature verification (`eth_account`) to confirm the user controls the wallet they're linking.

---

## Scoring Engine

### Currency conversion for cross-platform financial amounts
Each connector stores bet amounts in the platform's native denomination. The `currency` field records what that denomination is:

| Platform   | Currency | Notes |
|------------|----------|-------|
| Kalshi     | USD      | Amounts stored in cents; divide by 100 for dollars |
| Polymarket | USDC     | ERC-20 stablecoin; tracks USD 1:1 by design but has occasionally depegged |
| Manifold   | MANA     | Play money — no real-world value; exclude from financial scoring |
| Metaculus  | —        | No financial stakes |

When a future connector adds a platform denominated in ETH or BTC (e.g. a crypto-native prediction market), the same pattern applies: store the amount and `currency` at ingest time, convert later.

Things to think through:
- The scoring engine should convert USDC, ETH, BTC, etc. to USD using the historical exchange rate at the `placed_at` timestamp, not the current rate. This matters for crypto-denominated bets placed years ago.
- A good data source for historical rates: CoinGecko API (`/coins/{id}/history?date=DD-MM-YYYY`) or CryptoCompare. Rates should be cached in a `fx_rates` table (currency, date, usd_rate) to avoid repeated external calls during scoring runs.
- MANA should be excluded from any financial scoring (P&L, ROI) since it has no real-world value. It can still be used for probability-based scoring (Brier score, calibration) since the bet amounts don't factor into those.
- Kalshi amounts are in cents — the scoring engine should normalise to dollars (divide by 100) before any cross-platform comparison.
- Consider storing a `amount_usd` cache column in the bets table, populated at scoring time and invalidated if the exchange rate source changes.

---

## Scoring & Badges

### Badge catalogue expansion
Current badges cover basic accuracy thresholds. Planned additions: domain specialist (top accuracy in a specific tag), prediction streak, top-10% on a platform, and contrarian (profitable bets made against the crowd).

### Score filtering by tag
Once tag whitelisting/blacklisting is implemented, the scoring engine should support computing scores scoped to a tag filter — so a user can have a global Brier score and also a domain-specific one (e.g. their NBA forecasting score separately from their macro score).

---

## Notifications

### Email and push delivery
The notification-service dispatcher has routing stubs for email and push notifications but no delivery implementation. Needs an email provider integration (e.g. Resend or SendGrid) and a push provider (e.g. Firebase FCM) for the `badge_earned`, `market_resolved`, and `leaderboard_change` event types.

---

## Infrastructure

### CORS restriction
The API gateway currently allows all origins (`allow_origins=["*"]`). This should be locked down to known frontend origins before production.

### Root `pyproject.toml`
Running all unit tests from the repo root requires a root-level `pyproject.toml` with `pytest` configured to discover all service test directories. Currently each service must be tested individually.
