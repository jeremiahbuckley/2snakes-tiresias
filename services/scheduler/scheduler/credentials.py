"""
Credential decryption for linked accounts.

The auth-service encrypts platform credentials with Fernet before storing them
in the `linked_accounts.credential_encrypted` column. The scheduler decrypts
them at runtime using the same symmetric key to make authenticated API calls.

Required env var:
    CREDENTIAL_ENCRYPTION_KEY — Fernet key (URL-safe base64-encoded 32 bytes).
    Generate a new key with:
        python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"

This key must be the same one used by the auth-service when it encrypts credentials.
In production it should be sourced from a secrets manager (e.g. AWS Secrets Manager,
HashiCorp Vault) rather than a plain environment variable.
"""

from __future__ import annotations

import logging
import os

logger = logging.getLogger(__name__)

_ENCRYPTION_KEY: str = os.environ.get("CREDENTIAL_ENCRYPTION_KEY", "")


def decrypt_credential(ciphertext: str | None) -> str | None:
    """
    Decrypt a Fernet-encrypted credential string.

    Args:
        ciphertext: The encrypted bytes stored in the DB, encoded as a UTF-8 string.

    Returns:
        The plaintext credential string, or None if decryption is not possible
        (missing key, empty input, or decryption error).
    """
    if not ciphertext:
        return None

    if not _ENCRYPTION_KEY:
        logger.warning(
            "CREDENTIAL_ENCRYPTION_KEY is not set — cannot decrypt per-user credentials. "
            "Syncs that require stored API keys/tokens will be skipped for affected users."
        )
        return None

    try:
        from cryptography.fernet import Fernet, InvalidToken

        f = Fernet(_ENCRYPTION_KEY.encode())
        return f.decrypt(ciphertext.encode()).decode()
    except Exception as exc:  # InvalidToken, ValueError, etc.
        logger.error("Failed to decrypt credential: %s", exc)
        return None
