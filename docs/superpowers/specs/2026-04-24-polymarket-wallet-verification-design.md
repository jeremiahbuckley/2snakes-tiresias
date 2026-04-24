# Polymarket Wallet-Ownership Verification

**Date:** 2026-04-24  
**Status:** Approved  
**Scope:** `services/auth-service`

## Problem

`verify_polymarket_credential(wallet_address, message, signature)` exists and works (EIP-191 recovery via `eth_account`), but Polymarket is listed in `VERIFICATION_SKIPPED` because the API only accepts 2 fields from the client (`external_identifier` + `credential`). The verifier needs a 3rd field — the message the user signed — which is never sent. As a result, all Polymarket accounts are stored with `is_verified=False` and ownership is never confirmed.

## Goal

Enable real wallet-ownership verification during Polymarket account linking by accepting the signed message as a 3rd field and routing it to the existing verifier.

## Approach

Add an optional `message` field to `LinkedAccountIn`, pass it through `verify_upsert_credential`, and remove Polymarket from `VERIFICATION_SKIPPED`.

No platform-specific schemas, no DB changes, no migration.

## Changes

### 1. `auth_service/api.py` — `LinkedAccountIn`

Add one optional field:

```python
message: Optional[str] = Field(
    default=None,
    description="Message signed by the wallet (Polymarket only)",
)
```

Polymarket clients send:
- `external_identifier` = wallet address (`0x`-prefixed)
- `credential` = hex-encoded EIP-191 signature (`0x`-prefixed)
- `message` = the plaintext string the user signed

All other platforms send as before; `message` is ignored.

### 2. `auth_service/api.py` — `upsert_linked_account`

Pass the new field to the verifier dispatcher:

```python
verification = await verify_upsert_credential(
    platform, body.external_identifier, body.credential, message=body.message
)
```

### 3. `auth_service/linked_accounts.py` — `verify_upsert_credential`

Add `message: Optional[str] = None` parameter. Remove Polymarket from `VERIFICATION_SKIPPED`. Add dispatch case:

```python
if platform is Platform.POLYMARKET:
    if not message:
        raise ValueError("message is required for Polymarket wallet verification")
    return await verify_polymarket_credential(external_identifier, message, credential)
```

Remove Polymarket from the `VERIFICATION_SKIPPED` frozenset and update the docstring comment accordingly.

## Data Flow

```
Client: PUT /auth/me/linked-accounts/polymarket
  body: { external_identifier: "0x<wallet>", credential: "0x<sig>", message: "link this wallet to tiresias" }

upsert_linked_account
  → verify_upsert_credential(POLYMARKET, wallet, sig, message=msg)
      → verify_polymarket_credential(wallet, msg, sig)
          → eth_account: recover signer from sig over msg
          → compare recovered == wallet (case-insensitive)
          → True / False / raises ValueError

  True  → stored with is_verified=True, 200
  False → HTTPException 400 "polymarket rejected the provided credentials"
  ValueError (missing message, malformed sig) → HTTPException 400
```

## Storage

No DB schema changes. After successful verification:
- `external_identifier` = wallet address
- `credential_encrypted` = encrypted(signature)
- `is_verified` = `True`

The `message` is not persisted — it is only used for the one-time proof-of-ownership check.

## Error Handling

| Condition | Result |
|-----------|--------|
| `message` omitted for Polymarket | `ValueError` → 400 |
| Signature doesn't match wallet | `False` → 400 |
| Malformed signature hex | `ValueError` from `eth_account` → 400 |
| `wallet_address` or `credential` empty | `ValueError` from existing guard → 400 |

## Testing

### Update existing tests (`test_upsert_linked_account.py`)

- `test_skipped_verification_stores_with_is_verified_false`: Polymarket no longer skips. Replace with a test passing a real signed message, asserting `is_verified=True`.
- `test_polymarket_end_to_end_skips_verification`: Remove; replace with a test that exercises the real 3-field dispatch and confirms `is_verified=True`.

### New tests (`test_linked_accounts.py` — dispatch layer)

- `verify_upsert_credential` with Polymarket + valid 3-field input → `True`
- `verify_upsert_credential` with Polymarket + `message=None` → `ValueError`
- `verify_upsert_credential` with Polymarket + mismatched signature → `False`

The existing `TestVerifyPolymarket` suite already covers the verifier itself thoroughly; these new tests only cover the dispatch layer.

## Out of Scope

- CLOB L2 authentication (`apiKey`, `secret`, `passphrase`) — out of scope for this project (read-only data aggregation)
- A canonical fixed message string — clients may send any message; what matters is proving they signed it
- Strategy pattern refactor — deferred until more platforms need variant verification flows
