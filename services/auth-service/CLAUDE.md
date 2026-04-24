# auth-service

Handles user registration, login, JWT issuance/validation, user profiles, and external platform account linking.

## Tech Stack
- Python 3.12, FastAPI, PyJWT, passlib[bcrypt], cryptography (Fernet), sqlalchemy (via data-layer)

## Key Files
```
auth_service/
  api.py              # FastAPI router — all auth + profile + linked account endpoints
  jwt.py              # create_access_token(), decode_token(), get_current_user() FastAPI dep
  linked_accounts.py  # link/unlink platform credentials; Fernet encryption of API keys
```

## API Endpoints
```
POST /auth/register          # {email, username, password} → {access_token}
POST /auth/login             # {email, password} → {access_token}
GET  /auth/me                # current user profile (requires Bearer token)
PUT  /auth/me                # update display_name / notification prefs
POST /auth/link/{platform}   # link external account credentials
GET  /auth/linked-accounts   # list linked platforms
DELETE /auth/link/{platform} # unlink platform
```

## JWT
- HS256, secret from `JWT_SECRET` env var
- Default expiry: 24h (configurable via `JWT_EXPIRY_HOURS`)
- Payload: `{sub: user_id, exp, iat}`
- `get_current_user(token: str, db)` — FastAPI dependency used across all protected routes

## Credential Encryption
- All external API keys/tokens encrypted with Fernet (`CREDENTIAL_ENCRYPTION_KEY` env var) before DB storage
- `linked_accounts.py` handles encrypt-on-store, decrypt-on-read

## Credential Verification
- `linked_accounts.py` exposes async per-platform verifiers that make a lightweight authenticated call to confirm a credential before we trust it
- Market platforms implemented: Kalshi (RSA-PSS signed GET /portfolio/fills), Polymarket (EIP-191 signature recovery, no HTTP), Manifold (GET /v0/me), Metaculus (GET /api/users/me/)
- Social platforms (X, Bluesky) still raise `NotImplementedError` — deferred, see `FUTURE_FEATURES.md`
- Contract: verifiers return `False` for credential-rejection responses (401/403/signature mismatch), raise `ValueError`/`httpx.HTTPError` for caller errors and network failures
- `upsert_linked_account` calls `verify_upsert_credential` (dispatcher in `linked_accounts.py`). Policy:
  - verifier returns True  → `is_verified=True`, 200
  - verifier returns False → HTTPException 400, nothing stored
  - verifier raises (network/5xx) → stored with `is_verified=False` (don't block on upstream outages)
  - Polymarket → 3-field EIP-191: `verify_upsert_credential(POLYMARKET, wallet_address, signature, message=signed_text)`; stored with `is_verified=True` on success
  - X / Bluesky → skipped (listed in `VERIFICATION_SKIPPED`); stored with `is_verified=False`

## Dependencies
- Imports from `data-layer`: `data.crud.user`, `data.models.user.User`, `data.models.linked_account.LinkedAccount`
- Router mounted by `services/api-gateway`

## Env Vars
- `JWT_SECRET` — required, HS256 signing key
- `JWT_EXPIRY_HOURS` — optional, default 24
- `CREDENTIAL_ENCRYPTION_KEY` — required, Fernet key for encrypting stored credentials
