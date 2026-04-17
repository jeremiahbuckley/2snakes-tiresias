# User Personas

Tiresias has four personas. Two are active in the current codebase, two are sketched by
the schema and the deferred-work list but don't have working UI or API paths yet.

Workflows for each persona live in [workflows.md](workflows.md).

---

## 1. The Forecaster

**Who they are.** Someone who already trades or forecasts on one or more prediction
market platforms (Kalshi, Polymarket, Manifold, Metaculus) and wants a single
cross-platform view of their accuracy — a durable track record they can show off.

**Why they're here.** The platforms themselves don't tell you, in any comparable way,
how accurate you are. Tiresias computes platform-agnostic accuracy (Brier score,
calibration, Brier Skill Score), unifies a disparate prediction history, and turns
that into badges and a shareable profile.

**What the code knows about them.** This is the only authenticated persona today. They
live in the `users` table. Everything under `auth-service` (`POST /auth/register`,
`POST /auth/login`, `/auth/me/*`, linked accounts, share tokens, notification
preferences) is built for this persona, and the `user-dashboard` SvelteKit app is their
home.

**What they do.**
- Sign up, link one or more platform accounts.
- Watch markets resolve and their Brier / calibration / BSS numbers update.
- Earn badges (First Prediction, Well Calibrated, Cross-Platform Forecaster, etc.).
- Share their track record either as a public profile (`/u/:username`) or as an
  anonymous link with per-token visibility (`/share/:token`).
- Tune email notifications (resolution emails, badge emails, rank-change emails).

**Primary surfaces.**
- `apps/user-dashboard` — private SvelteKit app (http://localhost:5173 by default).
- `/auth/*` endpoints on the api-gateway.

**Open questions / caveats.**
- Credential encryption on the write path isn't plumbed through the auth-service yet
  (`PUT /auth/me/linked-accounts/{platform}` stores the credential in plaintext; the
  scheduler expects Fernet-encrypted blobs). Seeding a working linked account currently
  requires `scripts/cred.py`. See [setup.md](setup.md).
- Social publishing to X / Bluesky is part of the long-term story for this persona but
  is intentionally deferred — see [FUTURE_FEATURES.md](../FUTURE_FEATURES.md).

---

## 2. The Casual Observer

**Who they are.** Anyone on the internet with a link — usually someone the forecaster
shared their profile with, or a visitor who landed on the leaderboard via search or
social.

**Why they're here.** They want to see how good a specific forecaster is, or who the
best forecasters overall are. They're not here to forecast themselves; they may not
even know what a prediction market is.

**What the code knows about them.** Nothing persistent. They're never authenticated.
They consume exactly what the forecaster has opted to share:
- A *public profile* (planned: `/u/:username`) shows whatever the forecaster marked
  public on their own profile.
- A *share token* (`/share/:token`) shows whichever of `show_scores`, `show_badges`,
  `show_predictions` the forecaster enabled when they created it. Identity fields
  (email, username, display name) are never included in a share-token payload —
  `services/auth-service/auth_service/api.py::resolve_share_token` is explicit about
  that.
- The *leaderboard* (planned) shows a ranked list of forecasters by Brier Skill Score
  or Brier score.

**Primary surfaces.**
- `apps/public-leaderboard` — public SvelteKit app.
- `apps/public-profile` — public SvelteKit app.
- `GET /auth/share/{token}` on the api-gateway (implemented).
- `GET /leaderboard/...` and `GET /u/:username` endpoints on the api-gateway (not yet
  mounted — the leaderboard and user router are TODOs in `api-gateway/app.py`).

**Open questions / caveats.**
- There is no `is_public_profile` flag on the `users` model yet. The schema implies
  public profiles go through share tokens exclusively; a first-class `/u/:username` flow
  likely needs a small schema change.

---

## 3. The Operator / Admin (future)

**Who they are.** The person running the Tiresias deployment — today, just the
maintainer running `python -m scheduler.runner` on their own laptop. Long-term, a small
team handling user support, manual re-syncs, and incident triage.

**Why they're here.** Syncs fail. Credentials go stale. A user reports "my prediction
from yesterday isn't showing up" and the operator needs to trigger an on-demand sync
for just that user. Jobs get stuck; the operator needs to see why.

**What the code knows about them.** Today, very little. The capability exists as
library functions — `sync_user_predictions(user_id)` in `services/scheduler/scheduler/jobs.py`
can be called ad-hoc from a Python REPL — but there's no API surface, no authentication
role, and no UI. The MEMORY.md notes the "open a Python REPL, set DATABASE_URL first,
import scheduler.jobs" workflow; that's the de facto admin interface.

**What they'd do, once there's a surface.**
- Trigger `sync_user_predictions(user_id)` on demand.
- Inspect the most recent run of each recurring job.
- Tail the scheduler's log for a specific user.
- Revoke a share token on a user's behalf.
- Mark a linked account as unverified if its stored credential stops working.

**Primary surfaces (none yet).**
- `scripts/` — CLI-shaped operator tooling lives here. `cred.py` and
  `test_metaculus_live.py` are the precedent.
- Eventual `/admin/*` routes on the api-gateway with a role gate on the JWT.

**Open questions / caveats.**
- No `role` column exists on `users` yet. Building out admin requires either a schema
  change, a separate admin DB/auth mechanism, or an operator-only CLI that bypasses the
  gateway entirely.

---

## 4. The API Consumer / Embedder (future)

**Who they are.** A third party — a forecaster's personal website, a social profile
page, a tournament organiser's dashboard — that wants to embed or resurface a
forecaster's Tiresias track record somewhere else.

**Why they're here.** A forecaster has a shareable, verifiable accuracy record; the
embedder wants to pull that into their own site. Think: a blogger who wants their
current Brier Skill Score rendered in their sidebar, or a Twitter bot that toots badges
as they're earned.

**What the code knows about them.** Also nothing persistent — they're an anonymous HTTP
client. The intended surface is the existing share-token endpoint (`GET /auth/share/{token}`),
which returns a JSON payload scoped to the token's visibility settings. That's already
shippable; what's missing is any notion of documented external contract, versioning,
or rate limits.

**What they'd do.**
- Call `GET /auth/share/{token}` on a cadence to render a forecaster's scores and
  badges inline on a third-party site.
- (Future) Call `GET /leaderboard?limit=…&offset=…` to embed a ranked list.
- (Future) Subscribe to webhook notifications when a forecaster earns a badge or their
  rank changes, to render fresh social content automatically.

**Primary surfaces.**
- `GET /auth/share/{token}` today.
- A documented, stable `/public/*` or `/v1/*` namespace later, with rate limits.

**Open questions / caveats.**
- There is no public API contract document today. A real API-consumer persona needs
  versioning and a rate limiter before it's anything but an implicit, best-effort
  surface.

---

## Summary table

| Persona | Implemented? | Auth | Primary surface |
|---|---|---|---|
| Forecaster | Yes | JWT | `user-dashboard` + `/auth/*` |
| Casual Observer | Partial (share tokens only) | None | `public-profile` + `public-leaderboard` |
| Operator | No UI yet | (future) admin role | `scripts/*` + future `/admin/*` |
| API Consumer | Share tokens only | None | `GET /auth/share/{token}` + future public API |
