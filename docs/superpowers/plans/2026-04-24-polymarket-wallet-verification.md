# Polymarket Wallet-Ownership Verification Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Enable real EIP-191 wallet-ownership verification during Polymarket account linking by adding a `message` field to the link request and routing it through the existing verifier.

**Architecture:** Add `message: Optional[str]` to `LinkedAccountIn`, pass it through `verify_upsert_credential` as a keyword argument, remove Polymarket from `VERIFICATION_SKIPPED`, and add a Polymarket dispatch case that calls the already-implemented `verify_polymarket_credential`. No DB schema changes; no migration.

**Tech Stack:** Python 3.12, FastAPI, Pydantic v2, eth-account (EIP-191 signature recovery), pytest-asyncio

---

## File Map

| File | Change |
|------|--------|
| `services/auth-service/auth_service/linked_accounts.py` | Add `message` param to `verify_upsert_credential`; remove Polymarket from `VERIFICATION_SKIPPED`; add Polymarket dispatch |
| `services/auth-service/auth_service/api.py` | Add `message` field to `LinkedAccountIn`; pass `message=body.message` to `verify_upsert_credential` |
| `services/auth-service/tests/test_linked_accounts.py` | Add `TestVerifyUpsertCredentialPolymarket` class with 3 dispatch-layer tests |
| `services/auth-service/tests/test_upsert_linked_account.py` | Update skipped-platform test to use `Platform.X`; replace `test_polymarket_end_to_end_skips_verification` with a 3-field verified test |

---

## Task 1: Add 3-field dispatch for Polymarket in `verify_upsert_credential`

**Files:**
- Modify: `services/auth-service/auth_service/linked_accounts.py`
- Test: `services/auth-service/tests/test_linked_accounts.py`

All tests run from the repo root: `cd /path/to/2snakes-scratch`

- [ ] **Step 1: Write the three failing dispatch tests**

Append this class to `services/auth-service/tests/test_linked_accounts.py`, after the existing `TestVerifiersRegistry` class:

```python
# ---------------------------------------------------------------------------
# verify_upsert_credential — Polymarket dispatch (3-field path)
# ---------------------------------------------------------------------------

class TestVerifyUpsertCredentialPolymarket:
    def _sign(self, message: str) -> tuple[str, str]:
        """Generate a throwaway eth key, sign `message`, return (address, sig_hex)."""
        from eth_account import Account
        from eth_account.messages import encode_defunct

        acct = Account.create()
        signed = Account.sign_message(encode_defunct(text=message), private_key=acct.key)
        return acct.address, signed.signature.hex()

    async def test_valid_three_fields_returns_true(self) -> None:
        address, signature = self._sign("link this wallet to tiresias")
        result = await la.verify_upsert_credential(
            la.Platform.POLYMARKET, address, signature, message="link this wallet to tiresias"
        )
        assert result is True

    async def test_missing_message_raises_valueerror(self) -> None:
        with pytest.raises(ValueError, match="message is required"):
            await la.verify_upsert_credential(
                la.Platform.POLYMARKET, "0x1234", "0xsig"
            )

    async def test_mismatched_message_returns_false(self) -> None:
        address, signature = self._sign("hello")
        result = await la.verify_upsert_credential(
            la.Platform.POLYMARKET, address, signature, message="goodbye"
        )
        assert result is False
```

- [ ] **Step 2: Run the new tests to confirm they fail**

```bash
pytest services/auth-service/tests/test_linked_accounts.py::TestVerifyUpsertCredentialPolymarket -v
```

Expected: all 3 FAIL. `test_missing_message_raises_valueerror` will fail because the current code returns `None` (skip) instead of raising. The other two will fail because `verify_upsert_credential` doesn't accept a `message` keyword argument yet.

- [ ] **Step 3: Update `VERIFICATION_SKIPPED` — remove Polymarket**

In `services/auth-service/auth_service/linked_accounts.py`, replace the `VERIFICATION_SKIPPED` block and its preceding comment (lines ~318–323):

```python
# ---------------------------------------------------------------------------
# Platforms we skip verification for in the unified upsert flow
# ---------------------------------------------------------------------------
# - X / Bluesky: verifiers are still stubs (raise NotImplementedError).

VERIFICATION_SKIPPED: frozenset[Platform] = frozenset(
    {Platform.X, Platform.BLUESKY}
)
```

- [ ] **Step 4: Update `verify_upsert_credential` — add `message` param and Polymarket dispatch**

In `services/auth-service/auth_service/linked_accounts.py`, replace the entire `verify_upsert_credential` function (starting at `async def verify_upsert_credential`) with:

```python
async def verify_upsert_credential(
    platform: Platform, external_identifier: str, credential: str, *, message: Optional[str] = None
) -> bool | None:
    """
    Unified dispatch used by ``upsert_linked_account``.

    Returns:
        True   — verified OK.
        False  — platform rejected the credential (credentials are invalid).
        None   — verification skipped (platform in VERIFICATION_SKIPPED, or
                 unexpected error reached the verifier — see contract).

    Raises:
        httpx.HTTPError — network / upstream 5xx. Caller may treat this as
                          "accept but mark unverified" to avoid blocking on
                          upstream outages.
        ValueError      — malformed input (empty required field, bad PEM,
                          missing message for Polymarket).

    Per-platform argument mapping:
        Kalshi     → (external_identifier=key_id, credential=PEM)
        Manifold   → (credential=api_key)
        Metaculus  → (credential=token)
        Polymarket → (external_identifier=wallet_address, credential=signature, message=signed_text)
        X/Bluesky  → skipped (stubs)
    """
    if platform in VERIFICATION_SKIPPED:
        return None

    if platform is Platform.POLYMARKET:
        if not message:
            raise ValueError("message is required for Polymarket wallet verification")
        return await verify_polymarket_credential(external_identifier, message, credential)
    if platform is Platform.KALSHI:
        return await verify_kalshi_credential(external_identifier, credential)
    if platform is Platform.MANIFOLD:
        return await verify_manifold_credential(credential)
    if platform is Platform.METACULUS:
        return await verify_metaculus_credential(credential)

    logger.warning("No upsert-verifier mapping for platform=%s; skipping", platform)
    return None
```

Note: `Optional` is already imported at the top of `linked_accounts.py` via `from typing import Awaitable, Callable, Union` — add `Optional` to that import line:

```python
from typing import Awaitable, Callable, Optional, Union
```

- [ ] **Step 5: Run the new tests to confirm they pass**

```bash
pytest services/auth-service/tests/test_linked_accounts.py::TestVerifyUpsertCredentialPolymarket -v
```

Expected: all 3 PASS.

- [ ] **Step 6: Run the full test suite for the module to check for regressions**

```bash
pytest services/auth-service/tests/test_linked_accounts.py -v
```

Expected: all tests PASS, including the existing `TestVerifyPolymarket` and `TestVerifiersRegistry` classes.

- [ ] **Step 7: Commit**

```bash
git add services/auth-service/auth_service/linked_accounts.py \
        services/auth-service/tests/test_linked_accounts.py
git commit -m "feat: add 3-field Polymarket dispatch to verify_upsert_credential"
```

---

## Task 2: Add `message` field to `LinkedAccountIn` and wire the call site

**Files:**
- Modify: `services/auth-service/auth_service/api.py`
- Test: `services/auth-service/tests/test_upsert_linked_account.py`

- [ ] **Step 1: Update the skipped-platform test to use `Platform.X`**

In `services/auth-service/tests/test_upsert_linked_account.py`, replace `test_skipped_verification_stores_with_is_verified_false` with:

```python
async def test_skipped_verification_stores_with_is_verified_false() -> None:
    user = _make_user()
    db = _make_db(existing_account=None)

    # verify_upsert_credential returns None for skipped platforms (X, Bluesky).
    with patch("auth_service.api.verify_upsert_credential", AsyncMock(return_value=None)):
        out = await upsert_linked_account(Platform.X, _body(), user, db)

    assert out.is_verified is False
    assert db.add.called
```

- [ ] **Step 2: Replace the old Polymarket skip test with a 3-field verified test**

In `services/auth-service/tests/test_upsert_linked_account.py`, replace `test_polymarket_end_to_end_skips_verification` with:

```python
async def test_polymarket_end_to_end_verifies_with_three_fields() -> None:
    """
    Full stack test: real verify_upsert_credential dispatch (no mock) for Polymarket.
    Confirms a valid wallet signature produces is_verified=True.
    """
    from eth_account import Account
    from eth_account.messages import encode_defunct

    acct = Account.create()
    msg = "link this wallet to tiresias"
    signed = Account.sign_message(encode_defunct(text=msg), private_key=acct.key)
    signature = signed.signature.hex()

    user = _make_user()
    db = _make_db(existing_account=None)

    out = await upsert_linked_account(
        Platform.POLYMARKET,
        LinkedAccountIn(
            external_identifier=acct.address,
            credential=signature,
            message=msg,
            is_enabled=True,
        ),
        user,
        db,
    )

    assert out.is_verified is True
    assert out.platform == "polymarket"
    assert db.add.called
```

- [ ] **Step 3: Run the new test to confirm it fails**

```bash
pytest services/auth-service/tests/test_upsert_linked_account.py::test_polymarket_end_to_end_verifies_with_three_fields -v
```

Expected: FAIL — `assert out.is_verified is True` will fail with `False` because `body.message` isn't being passed to `verify_upsert_credential` yet (and `LinkedAccountIn` doesn't have the field yet, so it's silently dropped by Pydantic).

- [ ] **Step 4: Add `message` field to `LinkedAccountIn`**

In `services/auth-service/auth_service/api.py`, replace the `LinkedAccountIn` class with:

```python
class LinkedAccountIn(BaseModel):
    external_identifier: str = Field(max_length=256)
    credential: str = Field(description="API key, OAuth token, or app password (plaintext — encrypted server-side)")
    message: Optional[str] = Field(default=None, description="Message signed by the wallet (Polymarket only)")
    is_enabled: bool = True
```

- [ ] **Step 5: Pass `message` through in `upsert_linked_account`**

In `services/auth-service/auth_service/api.py`, inside `upsert_linked_account`, replace the `verify_upsert_credential` call:

```python
        verification = await verify_upsert_credential(
            platform, body.external_identifier, body.credential, message=body.message
        )
```

- [ ] **Step 6: Run the new test to confirm it passes**

```bash
pytest services/auth-service/tests/test_upsert_linked_account.py::test_polymarket_end_to_end_verifies_with_three_fields -v
```

Expected: PASS.

- [ ] **Step 7: Run the full test suites for both test files**

```bash
pytest services/auth-service/tests/test_upsert_linked_account.py services/auth-service/tests/test_linked_accounts.py -v
```

Expected: all tests PASS.

- [ ] **Step 8: Commit**

```bash
git add services/auth-service/auth_service/api.py \
        services/auth-service/tests/test_upsert_linked_account.py
git commit -m "feat: add message field to LinkedAccountIn and enable Polymarket verification"
```
