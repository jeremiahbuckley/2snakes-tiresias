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
- **Note**: Credential verifiers (actually calling platform APIs to validate keys) are stubs — not yet implemented

## Dependencies
- Imports from `data-layer`: `data.crud.user`, `data.models.user.User`, `data.models.linked_account.LinkedAccount`
- Router mounted by `services/api-gateway`

## Env Vars
- `JWT_SECRET` — required, HS256 signing key
- `JWT_EXPIRY_HOURS` — optional, default 24
- `CREDENTIAL_ENCRYPTION_KEY` — required, Fernet key for encrypting stored credentials
