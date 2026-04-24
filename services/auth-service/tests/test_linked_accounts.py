"""
Unit tests for per-platform credential verifiers in auth_service.linked_accounts.

Covers the four market-platform verifiers:
  * verify_kalshi_credential      — RSA-PSS signing + mocked HTTP response
  * verify_polymarket_credential  — real eth_account signature round-trip
  * verify_manifold_credential    — mocked HTTP response
  * verify_metaculus_credential   — mocked HTTP response

HTTP calls are mocked with ``unittest.mock`` (patching the module's
``httpx`` import); no network activity occurs during these tests.
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest

from auth_service import linked_accounts as la


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _mock_response(status_code: int, json_body: dict | None = None) -> MagicMock:
    """Build a mock httpx.Response with the given status_code."""
    resp = MagicMock(spec=httpx.Response)
    resp.status_code = status_code
    resp.json.return_value = json_body or {}
    resp.request = MagicMock(spec=httpx.Request)

    def _raise_for_status() -> None:
        if 400 <= status_code < 600:
            raise httpx.HTTPStatusError(
                f"{status_code}", request=resp.request, response=resp
            )

    resp.raise_for_status.side_effect = _raise_for_status
    return resp


def _patch_http_get(response: MagicMock):
    """Context manager that makes httpx.AsyncClient().get(...) return `response`."""
    async_client = AsyncMock()
    async_client.get = AsyncMock(return_value=response)

    # The module uses `async with httpx.AsyncClient(...) as client:`
    ctx = AsyncMock()
    ctx.__aenter__.return_value = async_client
    ctx.__aexit__.return_value = None

    return patch.object(la.httpx, "AsyncClient", return_value=ctx)


# ---------------------------------------------------------------------------
# Kalshi
# ---------------------------------------------------------------------------

def _generate_kalshi_pem() -> bytes:
    """Generate a throwaway RSA key for tests that need a valid signable PEM."""
    from cryptography.hazmat.primitives import serialization
    from cryptography.hazmat.primitives.asymmetric import rsa

    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    return key.private_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PrivateFormat.PKCS8,
        encryption_algorithm=serialization.NoEncryption(),
    )


class TestVerifyKalshi:
    async def test_happy_path_returns_true(self) -> None:
        pem = _generate_kalshi_pem()
        with _patch_http_get(_mock_response(200)):
            assert await la.verify_kalshi_credential("key-id-abc", pem) is True

    async def test_401_returns_false(self) -> None:
        pem = _generate_kalshi_pem()
        with _patch_http_get(_mock_response(401)):
            assert await la.verify_kalshi_credential("key-id-abc", pem) is False

    async def test_403_returns_false(self) -> None:
        pem = _generate_kalshi_pem()
        with _patch_http_get(_mock_response(403)):
            assert await la.verify_kalshi_credential("key-id-abc", pem) is False

    async def test_500_raises(self) -> None:
        pem = _generate_kalshi_pem()
        with _patch_http_get(_mock_response(500)):
            with pytest.raises(httpx.HTTPStatusError):
                await la.verify_kalshi_credential("key-id-abc", pem)

    async def test_empty_key_id_raises(self) -> None:
        pem = _generate_kalshi_pem()
        with pytest.raises(ValueError, match="key_id"):
            await la.verify_kalshi_credential("", pem)

    async def test_bad_pem_raises_valueerror(self) -> None:
        with pytest.raises(ValueError, match="PEM"):
            await la.verify_kalshi_credential("key-id-abc", b"not a real key")

    async def test_accepts_pem_as_string(self) -> None:
        pem = _generate_kalshi_pem().decode()
        with _patch_http_get(_mock_response(200)):
            assert await la.verify_kalshi_credential("key-id-abc", pem) is True


# ---------------------------------------------------------------------------
# Polymarket — real EIP-191 round-trip, no HTTP
# ---------------------------------------------------------------------------

class TestVerifyPolymarket:
    def _sign(self, message: str) -> tuple[str, str]:
        """Generate a throwaway eth key, sign `message`, return (address, sig_hex)."""
        from eth_account import Account
        from eth_account.messages import encode_defunct

        acct = Account.create()
        signed = Account.sign_message(encode_defunct(text=message), private_key=acct.key)
        return acct.address, signed.signature.hex()

    async def test_valid_signature_returns_true(self) -> None:
        address, signature = self._sign("link this wallet to tiresias")
        assert (
            await la.verify_polymarket_credential(
                address, "link this wallet to tiresias", signature
            )
            is True
        )

    async def test_lowercase_address_still_matches(self) -> None:
        address, signature = self._sign("hello")
        assert (
            await la.verify_polymarket_credential(address.lower(), "hello", signature) is True
        )

    async def test_wrong_address_returns_false(self) -> None:
        _, signature = self._sign("hello")
        # A different valid-looking address that definitely didn't sign.
        other = "0x0000000000000000000000000000000000000001"
        assert await la.verify_polymarket_credential(other, "hello", signature) is False

    async def test_wrong_message_returns_false(self) -> None:
        address, signature = self._sign("hello")
        assert await la.verify_polymarket_credential(address, "goodbye", signature) is False

    async def test_empty_args_raise(self) -> None:
        with pytest.raises(ValueError):
            await la.verify_polymarket_credential("", "msg", "0xabc")
        with pytest.raises(ValueError):
            await la.verify_polymarket_credential("0xabc", "", "0xabc")
        with pytest.raises(ValueError):
            await la.verify_polymarket_credential("0xabc", "msg", "")

    async def test_malformed_signature_raises_valueerror(self) -> None:
        with pytest.raises(ValueError):
            await la.verify_polymarket_credential(
                "0x0000000000000000000000000000000000000001",
                "hello",
                "not-a-signature",
            )


# ---------------------------------------------------------------------------
# Manifold
# ---------------------------------------------------------------------------

class TestVerifyManifold:
    async def test_happy_path_returns_true(self) -> None:
        with _patch_http_get(_mock_response(200, {"id": "user-1"})):
            assert await la.verify_manifold_credential("good-key") is True

    async def test_401_returns_false(self) -> None:
        with _patch_http_get(_mock_response(401)):
            assert await la.verify_manifold_credential("bad-key") is False

    async def test_500_raises(self) -> None:
        with _patch_http_get(_mock_response(500)):
            with pytest.raises(httpx.HTTPStatusError):
                await la.verify_manifold_credential("any-key")

    async def test_empty_key_raises(self) -> None:
        with pytest.raises(ValueError, match="api_key"):
            await la.verify_manifold_credential("")


# ---------------------------------------------------------------------------
# Metaculus
# ---------------------------------------------------------------------------

class TestVerifyMetaculus:
    async def test_happy_path_returns_true(self) -> None:
        with _patch_http_get(_mock_response(200, {"id": 42})):
            assert await la.verify_metaculus_credential("good-token") is True

    async def test_401_returns_false(self) -> None:
        with _patch_http_get(_mock_response(401)):
            assert await la.verify_metaculus_credential("bad-token") is False

    async def test_403_returns_false(self) -> None:
        with _patch_http_get(_mock_response(403)):
            assert await la.verify_metaculus_credential("bad-token") is False

    async def test_500_raises(self) -> None:
        with _patch_http_get(_mock_response(500)):
            with pytest.raises(httpx.HTTPStatusError):
                await la.verify_metaculus_credential("any-token")

    async def test_empty_token_raises(self) -> None:
        with pytest.raises(ValueError, match="token"):
            await la.verify_metaculus_credential("")


# ---------------------------------------------------------------------------
# Social stubs — still deferred
# ---------------------------------------------------------------------------

class TestSocialStubs:
    async def test_x_still_stubbed(self) -> None:
        with pytest.raises(NotImplementedError):
            await la.verify_x_credential("k", "s", "t", "ts")

    async def test_bluesky_still_stubbed(self) -> None:
        with pytest.raises(NotImplementedError):
            await la.verify_bluesky_credential("handle.bsky.social", "pw")


# ---------------------------------------------------------------------------
# Registry
# ---------------------------------------------------------------------------

class TestVerifiersRegistry:
    def test_all_platforms_have_a_verifier(self) -> None:
        for platform in la.Platform:
            assert platform in la.VERIFIERS
            assert callable(la.VERIFIERS[platform])

    def test_market_verifiers_point_at_real_impls(self) -> None:
        # None of the market verifiers should still be the bare NotImplementedError stub.
        assert la.VERIFIERS[la.Platform.KALSHI] is la.verify_kalshi_credential
        assert la.VERIFIERS[la.Platform.POLYMARKET] is la.verify_polymarket_credential
        assert la.VERIFIERS[la.Platform.MANIFOLD] is la.verify_manifold_credential
        assert la.VERIFIERS[la.Platform.METACULUS] is la.verify_metaculus_credential


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
