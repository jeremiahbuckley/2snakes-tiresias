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

## Auth & Account Linking

### Credential encryption at rest
External platform credentials (Kalshi key path, Manifold API key, Metaculus token, Polymarket wallet address) are currently stored as plaintext in the linked accounts table. These should be encrypted at rest using a server-side key (e.g. via Fernet or AWS KMS).

### Polymarket wallet verification
Polymarket auth is wallet-based rather than API-key-based. The auth-service needs to implement EIP-712 signature verification (`eth_account`) to confirm the user controls the wallet they're linking.

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
