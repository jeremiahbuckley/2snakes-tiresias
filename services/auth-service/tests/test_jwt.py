"""Unit tests for JWT token creation and validation."""

import pytest
import jwt as pyjwt
from auth_service.jwt import create_access_token, decode_access_token


def test_create_and_decode():
    token = create_access_token(user_id="user-abc")
    payload = decode_access_token(token)
    assert payload["sub"] == "user-abc"


def test_extra_claims():
    token = create_access_token(user_id="user-abc", extra_claims={"role": "admin"})
    payload = decode_access_token(token)
    assert payload["role"] == "admin"


def test_invalid_token_raises():
    with pytest.raises(pyjwt.InvalidTokenError):
        decode_access_token("not.a.valid.token")
