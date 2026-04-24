# Future Features

Tracked ideas and deferred work for Tiresias. Items here are intentionally out of scope for v1 but should be considered before or shortly after launch.

---

## Immediate Next Steps

1. **Run contract test suite** — `cd apps/user-dashboard && npm run test:contract` to confirm all 16 contract tests pass end-to-end
2. **Run smoke tests** — requires full stack (API on 8000, dev server on 5173, `.env.test` with TEST_USER credentials)
3. **Run Metaculus live smoke test** — fix linked_account row (is_enabled=true, correct integer Metaculus user ID, Fernet-encrypted token), then run `python scripts/test_metaculus_live.py --user-id <uuid>`
4. **Implement notification service handlers** — email via Resend/SendGrid/Postmark; see Notifications section below
5. **Implement auth service credential verifiers** — `verify_kalshi_credential` etc. all raise `NotImplementedError`
6. **Integration tests** — wire up `tests/integration/` with a real test DB
7. **Public leaderboard + public profile** frontend apps

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

### ~~Wire dashboard views to live database data~~ — DONE (2026-04-20)
`/dashboard`, `/predictions`, `/stats` loaders now call the api-gateway (`getDashboard`, `getPredictions`, `getUserStats`). `data_queries.py` implements the DB query layer. DevBypass amber banner added. See `docs/superpowers/plans/2026-04-20-live-dashboard-data.md`.

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

### Proactive registration validation & clearer duplicate-account errors
The auth-service register endpoint returns HTTP 409 on duplicate email or username (see `services/auth-service/auth_service/api.py::register`), and the dashboard's `/register` page surfaces the server's detail message in a banner. The gap is that the only feedback today arrives *after* the user submits — and it's a single generic line rather than per-field guidance.

Things to think through:
- Add a live username-availability check: a rate-limited `GET /auth/register/username-check?username=...` (returning 204 / 409) lets the form render a green check or red strike next to the field while the user is still typing. Debounce at ~400ms.
- Email is trickier — probing email existence is a user-enumeration risk. Consider only revealing an email conflict on full-form submit, not via a live endpoint.
- Per-field error rendering. Today's form has a single error banner; the server action should return a structured shape (`{ field: 'email' | 'username' | 'password', message: string }`) so the UI can highlight the offending input instead of asking the user to re-read a banner.
- Password strength feedback beyond the current "at least 8 characters" minimum (e.g. zxcvbn).
- A "forgot password" recovery flow — there is no recovery path today if the user loses their password. Out of scope for validation specifically, but naturally paired.

### Credential encryption at rest
External platform credentials (Kalshi key path, Manifold API key, Metaculus token, Polymarket wallet address) are currently stored as plaintext in the linked accounts table. These should be encrypted at rest using a server-side key (e.g. via Fernet or AWS KMS).

### Polymarket wallet linking (full flow)
Polymarket auth is wallet-based, not API-key-based, so we never see the user's private key — instead they prove ownership by signing a message with their wallet. The backend verifier is done; the frontend and plumbing around it are not. This likely spans multiple sessions.

**What's already done:**
- `auth_service.linked_accounts.verify_polymarket_credential(wallet_address, message, signature)` uses `eth_account.messages.encode_defunct` + `Account.recover_message` to do EIP-191 (`personal_sign`) recovery. Returns True iff the recovered signer matches the claimed address. Fully unit-tested with real sign→recover round-trips.
- Polymarket is listed in `linked_accounts.VERIFICATION_SKIPPED`, so the current upsert endpoint accepts a Polymarket account but stores it with `is_verified=False`. This keeps the old single-credential-field UI functional in the meantime.

**What's left (in rough order):**

1. **Nonce endpoint.** Add `GET /auth/me/link/polymarket/nonce` that returns a short-lived, user-bound challenge string to be signed — e.g. `"Link this wallet to Tiresias for user {user_id} at {iso_timestamp}. Nonce: {random_32_hex}"`. Store the nonce server-side (Redis or a `wallet_link_nonces` table) with a 5-minute TTL so signatures can't be replayed against a stale challenge. The verifier must later check both that the signature recovers to the claimed wallet *and* that the signed message equals an unexpired nonce issued to this user.

2. **Request schema extension.** The current `LinkedAccountIn` has one `credential` field. Polymarket needs three: `wallet_address`, `signed_message`, `signature`. Options: (a) add optional Polymarket-specific fields to `LinkedAccountIn` and branch on `platform` in the handler; (b) add a dedicated `PUT /auth/me/linked-accounts/polymarket` endpoint with its own schema. (b) is cleaner — the shape is genuinely different — and keeps the generic endpoint simple.

3. **Remove Polymarket from `VERIFICATION_SKIPPED`.** Once the new endpoint exists and collects the three fields, wire `verify_polymarket_credential` into the dispatcher for the Polymarket route.

4. **Frontend wallet-connect component.** The user-dashboard needs a Connect Wallet button that:
   - Detects `window.ethereum` (injected provider — MetaMask, Rainbow, Coinbase Wallet, etc.). Falls back to WalletConnect for users without a browser wallet.
   - Requests accounts: `eth_requestAccounts`.
   - Fetches a nonce from the backend.
   - Calls `personal_sign` on the nonce message.
   - POSTs `{wallet_address, signed_message, signature}` to the Polymarket link endpoint.
   - Handles user rejection, wrong network, locked wallet.

   Recommended library: **`viem`** (modern, tree-shakeable, TypeScript-native, used by wagmi v2) over `ethers.js` (larger bundle, older API). If we want hooks/state management on top, add **`wagmi`** — but for a single-button flow, raw viem is probably enough.

5. **Storage semantics.** For Polymarket, `credential_encrypted` is meaningless — we don't store a secret, just the verified wallet address in `external_identifier`. Either leave `credential_encrypted` empty for Polymarket rows, or store the signature as an audit trail (mild info leak, probably don't bother). Document the choice in the auth-service CLAUDE.md.

6. **Re-verification.** Unlike API keys, wallet signatures don't expire, so we can treat a Polymarket account as permanently verified once the initial link succeeds. The user can unlink + relink if they switch wallets. No re-verification cron needed.

**Things to think through:**
- The Data API endpoints we use (`/trades?user=<address>`, `/closed-positions?user=<address>`) are fully public and don't require the user's signature to read — so wallet verification is purely a "prove they own the wallet before we attribute trades to them" check, not an API-access check. This is a meaningful simplification: there's no "credential rotation" story.
- Chain selection. Polymarket runs on Polygon. The wallet-connect flow should probably force-switch to chain id 137 (or at least warn if the user is on a different chain), since the signature itself is chain-agnostic but users may be confused.
- EIP-712 (typed data) vs EIP-191 (personal_sign). Current implementation is EIP-191; the original note in this file said EIP-712. EIP-712 would show a nicely-typed prompt in MetaMask ("Link Wallet to Tiresias" as a structured form) but is more work to implement on both ends. EIP-191 is fine for v1.
- Mobile. Injected providers don't exist in mobile browsers. WalletConnect is the standard workaround — adds a QR code flow. Can be deferred to after desktop works.

---

## Sharing & Public Profiles

### X / Twitter handle verification on shared profiles
A share token URL (`/share/:token`) intentionally carries no identity — `resolve_share_token` in `services/auth-service/auth_service/api.py` is explicit about never returning email, username, or display name. That's good for privacy, but it creates an impersonation hole: anyone who obtains a share URL can post it on social media as "my predictions" and the viewer has no way to confirm the claimant is the actual forecaster.

The proposed feature: let a forecaster optionally bind one or more social identities (X / Twitter handle first, Bluesky and others later) to a share token, and let viewers confirm the binding without breaking the drop-a-link-and-go flow.

Things to think through:
- Binding shape. When the forecaster creates a share token, they can optionally enter a handle (`@alice`) and a proof URL — typically a tweet they post containing the share token slug or a short challenge string. The share page renders something like "Verified as @alice on X" with a link to the proof.
- Verifying the proof, in increasing strength:
  1. *Soft* — just display the claimed handle and link to the X profile. Viewers eyeball the tie. Near-zero implementation cost; near-zero fraud resistance, but better than the status quo.
  2. *Hard* — at token-creation time, fetch the proof URL, confirm its text contains the expected challenge string (e.g. `Linking Tiresias share XYZ123`), and only then mark the share token `is_verified=true`. Cache the result; viewers shouldn't trigger re-fetches. Needs either X's paid API tier or a light headless-browser scrape, both of which add operational weight.
- A simpler anti-copy defense that sidesteps the social API entirely: on the share page, render the X handle as a small text box and require the viewer to type it in to unlock the page. This isn't real verification — it just means a copycat would have to also paste in a matching handle when they share. Low-friction, mildly deterring, honest about what it isn't. Should be an opt-in toggle on the token, not the default — gating viewer access by default would break the "paste the link in a Discord channel" use case that's probably the dominant one.
- UI surfaces. The handle + proof field belongs on the share-token creation form in `/settings`. Verification status (verified / claimed-but-unverified / no handle) should appear in the share-token list so the forecaster can see which tokens carry which level of attestation.
- Bluesky as an easier v2. The AT Protocol supports domain-based identity — a forecaster can prove ownership of `alice.example.com` by adding a TXT record. That's much cleaner than scraping X, but the user base is smaller. Probably worth doing once X is shipped.
- Don't conflate this with the "public profile" route (`/u/:username`, sketched in personas.md). That page already shows the forecaster's chosen username, so identity is implicit. The verification problem is unique to anonymous share tokens.

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

### One-command local stack via `docker compose` (with profiles for partial stacks)
Starting the local stack today means six-ish terminal windows: Postgres (containerised), api-gateway (uvicorn), scheduler (python -m), and each of the three SvelteKit apps (vite dev). Every service already has a `Containerfile`, so the ingredients exist — `compose.yaml` just hasn't been extended past `db` and `migrate`. The goal is to let a developer run `docker compose up` (or one of a couple of grouped variants) for the stuff they aren't actively editing, and keep a single local process with hot reload for whatever they *are* editing.

Things to think through:
- Services to add to `compose.yaml`: `api-gateway`, `scheduler`, `user-dashboard`, `public-leaderboard`, `public-profile`. Each already has a `Containerfile` and a dedicated port (5173 / 5174 / 5175 for the three Vite apps; 8000 for the gateway). Map them to the host so URLs and existing docs keep working.
- Use [compose profiles](https://docs.docker.com/compose/how-tos/profiles/) to allow partial brings-up. Candidate profiles: `backend` (db, migrate, api-gateway, scheduler), `frontends` (the three SvelteKit apps), `all` (everything). Typical workflow: `docker compose --profile backend up -d` and then `npm run dev` locally in whichever app you're editing.
- Environment variables. Every service reads from `.env.local` today; compose should take it as an `env_file` (or `--env-file`) so the container processes see the same values. The `PYTHONPATH` tricks from `running.md` aren't needed inside containers because each service image bakes its own package layout.
- Internal networking. Services inside the compose network reach Postgres at `db:5432`, which means the macOS `127.0.0.1 + ?ssl=disable` workaround in `DATABASE_URL` only applies when a *host* process talks to the containerised DB. Document both cases clearly, perhaps with two presets in `.env.example`.
- Kalshi private key. The scheduler needs `KALSHI_PRIVATE_KEY_PATH` pointing at a real file. A bind mount like `-v "$KALSHI_PRIVATE_KEY_PATH:/secrets/kalshi.key:ro"` in the compose service definition keeps the key out of the image; alternatively use compose's `secrets:` block for the production-adjacent path.
- Dev vs prod images. The existing `Containerfile`s are built for shippable artifacts, not hot reload. To support "edit-and-see-it-live" in containers, add a `compose.dev.yaml` override that bind-mounts the source directory and runs uvicorn with `--reload` / vite in dev mode. The default `docker compose up` stays production-shaped; `docker compose -f compose.yaml -f compose.dev.yaml up` gives you the dev experience.
- Startup ordering. `api-gateway` and `scheduler` need the `migrate` one-shot to finish before they start. `depends_on` with `condition: service_completed_successfully` handles this cleanly.
- Logs. `docker compose logs -f` already tails everything; most developers will want to filter to one service (`docker compose logs -f scheduler`). Worth a one-liner in `running.md` once the compose setup lands.
- Wrapper scripts / `Makefile` / `justfile`. Not strictly required, but `make dev-backend`, `make dev-all`, `make logs` make the profile incantations discoverable. Keep as an optional nicety — the compose commands should work on their own.
- Document the new flow in `docs/running.md`. The existing "Starting things by hand" section stays (still the right answer when you're editing service code), but a new "Starting things with docker compose" section should come first for the common case.
