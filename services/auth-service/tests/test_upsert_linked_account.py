"""
Unit tests for the verifier-wiring in ``upsert_linked_account``.

Focus:
  - Verifier returns True  → account stored with is_verified=True, 200-equivalent
  - Verifier returns False → HTTPException(400), nothing stored
  - Verifier raises         → account stored with is_verified=False (don't block user)
  - Verification skipped   → account stored with is_verified=False
  - ValueError (malformed) → HTTPException(400)

DB interactions are mocked to keep these hermetic. We patch
``auth_service.api.verify_upsert_credential`` directly so each case
selects a specific verifier outcome.
"""

from __future__ import annotations

import datetime
import os
import uuid
from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest
from fastapi import HTTPException

from auth_service.api import LinkedAccountIn, upsert_linked_account
from data.models.linked_account import Platform

# A valid Fernet key for tests — must be set before api.py imports run.
_TEST_FERNET_KEY = "xwxGMFCEr6jQ3wGUUv3i4hCYPq2G4b7NNjl9rcKWQv8="


@pytest.fixture(autouse=True)
def set_encryption_key(monkeypatch):
    monkeypatch.setenv("CREDENTIAL_ENCRYPTION_KEY", _TEST_FERNET_KEY)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_user() -> MagicMock:
    """Minimal User stand-in — only id is read by the upsert."""
    user = MagicMock()
    user.id = uuid.uuid4()
    return user


def _make_db(existing_account: MagicMock | None) -> MagicMock:
    """Build an AsyncSession-shaped mock. `existing_account=None` → new row path."""
    db = AsyncMock()
    result = MagicMock()
    result.scalar_one_or_none = MagicMock(return_value=existing_account)
    db.execute = AsyncMock(return_value=result)
    db.add = MagicMock()
    db.commit = AsyncMock()

    # `db.refresh(account)` is expected to populate timestamp fields. We have
    # to simulate that for LinkedAccountOut.from_orm(acct.created_at).
    async def _refresh(obj) -> None:
        if not hasattr(obj, "created_at") or obj.created_at is None:
            obj.created_at = datetime.datetime(2026, 4, 18, 12, 0, 0)

    db.refresh = AsyncMock(side_effect=_refresh)
    return db


def _body(credential: str = "pem-or-key", identifier: str = "id-abc") -> LinkedAccountIn:
    return LinkedAccountIn(
        external_identifier=identifier,
        credential=credential,
        is_enabled=True,
    )


# ---------------------------------------------------------------------------
# Verified path
# ---------------------------------------------------------------------------

async def test_verifier_true_stores_with_is_verified_true() -> None:
    user = _make_user()
    db = _make_db(existing_account=None)

    with patch("auth_service.api.verify_upsert_credential", AsyncMock(return_value=True)):
        out = await upsert_linked_account(Platform.MANIFOLD, _body(), user, db)

    assert out.is_verified is True
    assert out.platform == "manifold"
    # Inserted (not updated)
    assert db.add.called
    assert db.commit.await_count == 1


# ---------------------------------------------------------------------------
# Rejection path — 400, nothing stored
# ---------------------------------------------------------------------------

async def test_verifier_false_raises_400_and_does_not_store() -> None:
    user = _make_user()
    db = _make_db(existing_account=None)

    with patch("auth_service.api.verify_upsert_credential", AsyncMock(return_value=False)):
        with pytest.raises(HTTPException) as exc:
            await upsert_linked_account(Platform.MANIFOLD, _body(), user, db)

    assert exc.value.status_code == 400
    assert "rejected" in exc.value.detail.lower()
    # No insert, no commit.
    assert not db.add.called
    assert db.commit.await_count == 0


# ---------------------------------------------------------------------------
# Network / upstream error — accept but mark unverified
# ---------------------------------------------------------------------------

async def test_verifier_network_error_stores_with_is_verified_false() -> None:
    user = _make_user()
    db = _make_db(existing_account=None)

    # Build a real-ish httpx.HTTPError (TransportError subclass)
    network_err = httpx.ConnectError("upstream down")

    with patch(
        "auth_service.api.verify_upsert_credential",
        AsyncMock(side_effect=network_err),
    ):
        out = await upsert_linked_account(Platform.KALSHI, _body(), user, db)

    assert out.is_verified is False
    assert db.add.called
    assert db.commit.await_count == 1


# ---------------------------------------------------------------------------
# Skipped verification — Polymarket & social stubs
# ---------------------------------------------------------------------------

async def test_skipped_verification_stores_with_is_verified_false() -> None:
    user = _make_user()
    db = _make_db(existing_account=None)

    # verify_upsert_credential returns None for skipped platforms (X, Bluesky).
    with patch("auth_service.api.verify_upsert_credential", AsyncMock(return_value=None)):
        out = await upsert_linked_account(Platform.X, _body(), user, db)

    assert out.is_verified is False
    assert db.add.called


# ---------------------------------------------------------------------------
# ValueError (malformed input) — 400
# ---------------------------------------------------------------------------

async def test_verifier_value_error_raises_400() -> None:
    user = _make_user()
    db = _make_db(existing_account=None)

    with patch(
        "auth_service.api.verify_upsert_credential",
        AsyncMock(side_effect=ValueError("Could not parse Kalshi private key PEM: bad")),
    ):
        with pytest.raises(HTTPException) as exc:
            await upsert_linked_account(Platform.KALSHI, _body(), user, db)

    assert exc.value.status_code == 400
    assert "kalshi" in exc.value.detail.lower()
    assert not db.add.called


# ---------------------------------------------------------------------------
# Update existing account (not insert)
# ---------------------------------------------------------------------------

async def test_update_existing_account_sets_is_verified_from_verifier() -> None:
    user = _make_user()
    existing = MagicMock()
    existing.external_identifier = "old-id"
    existing.credential_encrypted = "old-cred"
    existing.is_enabled = False
    existing.is_verified = False  # was unverified
    existing.platform = "manifold"
    existing.platform_type = "market"
    existing.created_at = datetime.datetime(2026, 1, 1)
    db = _make_db(existing_account=existing)

    with patch("auth_service.api.verify_upsert_credential", AsyncMock(return_value=True)):
        out = await upsert_linked_account(
            Platform.MANIFOLD,
            _body(credential="new-key", identifier="new-id"),
            user,
            db,
        )

    # Existing row mutated in place — no new add().
    assert not db.add.called
    assert existing.external_identifier == "new-id"
    assert existing.credential_encrypted != "new-key"  # stored encrypted, not plaintext
    assert existing.credential_encrypted != "old-cred"  # updated from the old value
    assert existing.is_enabled is True
    assert existing.is_verified is True  # verifier promoted it
    assert out.is_verified is True


# ---------------------------------------------------------------------------
# Metaculus — external_identifier auto-resolved to numeric user ID
# ---------------------------------------------------------------------------

async def test_metaculus_external_identifier_resolved_to_numeric_id() -> None:
    """Linking Metaculus with a username should store the numeric user ID instead."""
    user = _make_user()
    db = _make_db(existing_account=None)

    with (
        patch("auth_service.api.verify_upsert_credential", AsyncMock(return_value=True)),
        patch(
            "auth_service.api.resolve_metaculus_external_identifier",
            AsyncMock(return_value="98765"),
        ),
    ):
        out = await upsert_linked_account(
            Platform.METACULUS,
            _body(identifier="jeremiahbuckley"),
            user,
            db,
        )

    assert out.external_identifier == "98765"
    assert out.is_verified is True
    assert db.add.called


async def test_metaculus_external_identifier_falls_back_on_resolve_error() -> None:
    """If the ID-resolution call fails, fall back to whatever the user provided."""
    user = _make_user()
    db = _make_db(existing_account=None)

    with (
        patch("auth_service.api.verify_upsert_credential", AsyncMock(return_value=True)),
        patch(
            "auth_service.api.resolve_metaculus_external_identifier",
            AsyncMock(side_effect=Exception("network error")),
        ),
    ):
        out = await upsert_linked_account(
            Platform.METACULUS,
            _body(identifier="jeremiahbuckley"),
            user,
            db,
        )

    assert out.external_identifier == "jeremiahbuckley"
    assert out.is_verified is True
    assert db.add.called


# ---------------------------------------------------------------------------
# Per-platform routing — Polymarket verified with real EIP-191 signature
# ---------------------------------------------------------------------------

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
