# Workflows

Each section below walks through a single workflow end-to-end, citing the specific
functions and routes involved. Use this as a map from user-visible behaviour down to
the code that implements it.

The four personas are defined in [personas.md](personas.md).

---

## Forecaster workflows

### F1 — Sign up and link a market account

**Goal.** A new user registers, logs in, and connects one of their prediction market
accounts so Tiresias can start syncing their history.

**Steps.**

1. User hits the dashboard; clicks "Sign up".
2. Frontend posts to `POST /auth/register` with `email`, `username`, `password`, and
   optional `display_name`.
3. `auth-service` hashes the password (bcrypt via `passlib`), inserts the user, creates
   default `NotificationPreferences`, and issues a JWT. Handler:
   `auth_service.api.register`.
4. Frontend stores the JWT and calls `GET /auth/me` to hydrate the session.
5. User goes to settings and picks a platform to link.
6. Frontend calls `PUT /auth/me/linked-accounts/{platform}` with the platform's
   `external_identifier` (Kalshi key ID / Polymarket wallet / Manifold username /
   Metaculus user ID) and `credential` (the API key or token in plaintext). Handler:
   `auth_service.api.upsert_linked_account`.
7. A `LinkedAccount` row is written with `is_enabled=true`, `is_verified=false`.

**What the scheduler does next.** On the next `sync_markets` tick (every 15 min), the
user appears in `UserCRUD.list_active()`. The scheduler calls
`scheduler.sync.sync_one_user(user_id)`, which dispatches to the right per-platform sync
function (`_sync_kalshi`, `_sync_polymarket`, `_sync_manifold`, `_sync_metaculus`) for
each enabled linked account.

**Caveats.**
- The `PUT /auth/me/linked-accounts/{platform}` endpoint currently stores credentials
  **without** Fernet encryption (see the `TODO` at `auth_service/api.py:344`). The
  scheduler decrypts credentials with Fernet before use. Until that write path is
  fixed, seed rows via `scripts/cred.py encrypt` — see [setup.md](setup.md).
- Credential verification against the external platform is a stub
  (`verify_kalshi_credential` etc. raise `NotImplementedError`). `is_verified` stays
  `false` today.

---

### F2 — View the dashboard

**Goal.** A logged-in user sees their prediction history, Brier / calibration / BSS
numbers, badges, and linked-account status.

**Steps.**

1. User lands on `/dashboard`.
2. Frontend calls `GET /auth/me` (identity + profile).
3. Frontend calls the various read endpoints that will be mounted alongside auth-service
   — `/users/me/predictions`, `/users/me/scores`, `/users/me/badges` — to fill out the
   panels. (These routes live in the README's planned API surface; the badge-service
   `/badges` router is already written but not yet mounted on the gateway.)
4. User sees:
   - Paginated prediction history with resolution outcome and per-prediction Brier
     contribution.
   - Calibration curve: bucketed predicted probability vs. observed frequency. Computed
     by `scoring_engine.calibration.calibration_buckets`.
   - Summary stats: mean Brier, Brier Skill Score (vs. 0.5 baseline), Expected
     Calibration Error. Computed by `scoring_engine.engine.score_user`.
   - Earned badges with issuance timestamps. Sourced from `user_scores.badge_ids`.
   - Linked-account health: for each platform, `last_synced_at` and the
     `is_enabled` / `is_verified` flags.

**Underlying data.** `user_scores` is kept up to date by
`detect_and_score_resolutions` (every 5 min) on the incremental path, and by
`rebuild_leaderboard` (every 1 hour) on the full-recompute path. The dashboard reads
the row directly.

---

### F3 — Generate an anonymous share link

**Goal.** The forecaster wants to share their record on Twitter without revealing their
real identity.

**Steps.**

1. On `/settings`, user clicks "Generate share link".
2. User picks visibility: `show_scores`, `show_badges`, `show_predictions`.
3. Frontend posts to `POST /auth/me/share-tokens`. Handler:
   `auth_service.api.create_share_token`.
4. Auth-service generates a random URL-safe token
   (`data.models.share_token.generate_token`), inserts a `ShareToken` row with the
   chosen flags and `is_active=true`.
5. The response includes the token; frontend renders the full shareable URL.

**What the recipient sees.** When anyone GETs `/auth/share/{token_slug}`:

1. `auth_service.api.resolve_share_token` looks up the token, rejects expired or
   revoked ones.
2. It fetches the user's `UserScore` and returns **only** the fields the token opted
   into.
3. It explicitly does not return `email`, `username`, or `display_name` — the token is
   anonymous by design.

**Revocation.** `DELETE /auth/me/share-tokens/{token_slug}` flips `is_active=false`
(`auth_service.api.revoke_share_token`). The URL immediately starts returning 404.

---

### F4 — Manage email notifications

**Goal.** The forecaster opts out of "you earned a badge" emails but keeps resolution
emails.

**Steps.**

1. User visits `/settings/notifications`.
2. Frontend calls `GET /auth/me/notifications` to load the current three toggles
   (`email_on_resolution`, `email_on_badge`, `email_on_rank_change`). Handler:
   `auth_service.api.get_notification_prefs`.
3. User flips a toggle. Frontend posts a partial update to
   `PATCH /auth/me/notifications`. Handler: `auth_service.api.update_notification_prefs`.
4. The row in `notification_preferences` is updated.

**Next time the scheduler scores a resolution.** The notification-service dispatcher
checks the flag before rendering and sending the email. Today, the handlers
(`_handle_market_resolved`, `_handle_badge_earned`, `_handle_rank_change`) are
`NotImplementedError` stubs; the scheduler catches and ignores the error so scoring
continues.

### F4b — One-click unsubscribe (RFC 8058)

**Goal.** The forecaster unsubscribes from inside an email client without logging in.

**Steps.**

1. Outbound emails carry a signed JWT in a `List-Unsubscribe-Post` header that points
   at `/auth/notifications/unsubscribe?token=<jwt>`.
2. Gmail / Outlook render a native "Unsubscribe" button that POSTs to that URL.
3. `auth_service.api.unsubscribe_post` (and the corresponding GET) decodes the token,
   pulls `sub` (user UUID) and `pref` (which toggle to flip), and sets that preference
   to `false`. Implementation: `_apply_unsubscribe`.
4. The server returns the updated preferences.

Unsubscribe tokens are signed by the notification-service using `JWT_SECRET_KEY`, so
the same key must be in scope for both services.

---

## Casual-observer workflows

### O1 — Browse the leaderboard

**Goal.** A visitor sees the top forecasters by accuracy.

**Steps.**

1. Visitor lands on `apps/public-leaderboard`.
2. The page fetches (planned) `GET /leaderboard?limit=N&offset=M` from the api-gateway.
3. The response is a ranked list of forecasters by `brier_skill_score DESC`, with their
   `mean_brier_score`, `total_predictions`, and top badges.
4. Visitor can click a row to open that forecaster's public profile.

**Status.** The SvelteKit app exists in `apps/public-leaderboard`. The underlying
`/leaderboard` route is not yet mounted on the gateway — the `TODO` in
`services/api-gateway/api_gateway/app.py` covers this.

### O2 — Open a shared link

**Goal.** Someone clicks a forecaster's anonymous share link and sees a clean profile
page.

**Steps.**

1. Visitor navigates to `/share/<token>` on the `public-profile` app.
2. The page calls `GET /auth/share/{token}` (already implemented).
3. Auth-service resolves the token and returns the opted-in fields only.
4. The page renders scores / badges / predictions according to the flags the forecaster
   set, without any personal identifiers.

---

## Operator workflows (future)

### X1 — Trigger an on-demand sync for one user

**Today** — open a Python REPL with `PYTHONPATH` configured and `DATABASE_URL` set,
then:

```python
from scheduler.jobs import sync_user_predictions
import asyncio
asyncio.run(sync_user_predictions("<user-uuid>"))
```

The MEMORY.md notes a couple of gotchas: the REPL needs Enter pressed twice on
multi-line blocks, and `DATABASE_URL` must be set **before** importing `scheduler.jobs`
because the engine is built at import time.

**Future** — `POST /admin/sync/{user_id}` on the gateway, behind an admin role on the
JWT. Schema change required (`users.role`). No implementation yet.

### X2 — Rotate the credential-encryption key

**Today** — no automation. The scheduler and auth-service read `CREDENTIAL_ENCRYPTION_KEY`
from the environment at startup. Rotation would require decrypting every
`linked_accounts.credential_encrypted` with the old key and re-encrypting with the
new one before restart.

### X3 — Inspect a scheduler job run

**Today** — read logs. APScheduler logs each fire to stdout; grep for the job ID
(`sync_markets`, `score_resolutions`, `rebuild_leaderboard`).

**Future** — a small admin surface exposing `AsyncIOScheduler.get_jobs()` output and
the last-run status for each recurring job.

---

## API-consumer workflows (future)

### C1 — Embed a forecaster's badges on a third-party page

**Today** — the forecaster creates a share token with `show_badges=true`, pastes the
resulting `/auth/share/{token}` URL into their site's server code, and renders from the
JSON. No rate limit, no documented contract, no stability guarantee.

### C2 — Consume the public leaderboard

**Today** — the `/leaderboard` route isn't mounted on the gateway yet, so this is
aspirational.

**Future** — `GET /leaderboard?limit=N&offset=M&sort=bss` with documented pagination,
sorted by `brier_skill_score` or `mean_brier_score`. Would need to be moved under a
versioned namespace (`/v1/leaderboard`) before external consumers can rely on it.

---

## Background (system) workflow

### S1 — A market resolves, users get scored, badges fire, emails go out

This is the single most important runtime path. It's triggered by the
`detect_and_score_resolutions` job every 5 minutes.

```
detect_and_score_resolutions()
  │
  ├─ MarketCRUD.list_resolved_with_unscored_predictions()
  │     returns markets where resolved=true and at least one
  │     prediction hasn't yet been scored
  │
  ├─ group predictions by user_id
  │
  ├─ for each user:
  │     scoring_engine.score_user(user_id, predictions)
  │       ├─ brier.mean_brier_score()
  │       ├─ brier.brier_skill_score()                (baseline = 0.5)
  │       └─ calibration.expected_calibration_error()
  │
  │     UserScoreCRUD.upsert(user_id, result)
  │
  │     badge_service.evaluate_badges(result)
  │       iterates BADGES, calls each predicate on result
  │       returns the set of badge IDs the user now qualifies for
  │
  │     diff against the user's previous badge_ids
  │     → newly-earned and newly-revoked badges
  │
  │     UserScoreCRUD.update_badge_ids(user_id, new_set)
  │
  │     for each newly-earned badge:
  │       notification_service.dispatch(BadgeEarnedEvent(user_id, badge_id))
  │
  │     for each newly-resolved market in this user's batch:
  │       notification_service.dispatch(MarketResolvedEvent(user_id, market_id))
  │
  └─ notification_service.dispatcher
        for each event:
          1. check the user's NotificationPreferences row
          2. atomically claim an email_deliveries dedupe slot
          3. render the Jinja2 template
          4. send via Resend with a List-Unsubscribe header
          5. record the delivery's message_id or failure
```

**Why the diagram has `silently-swallows-NotImplementedError` as a footnote.** Because
the dispatcher handlers are stubs today, `dispatch()` raises `NotImplementedError` on
every call. The scheduler wraps the call in a try/except that logs and continues, so
scoring and badge issuance still complete — the visible user impact is just "no email
arrived".

### S2 — Weekly drift correction

Every hour, `rebuild_leaderboard` does a full recompute of every user's `UserScore`
row from the raw `predictions` table. This exists to prevent drift: the incremental
path in S1 can miss resolutions if a cron tick is missed or a job crashes midway. The
full recompute is idempotent and the authoritative source of truth for leaderboard
rankings.
