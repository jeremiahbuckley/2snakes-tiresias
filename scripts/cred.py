"""
Credential encryption/decryption helper for local dev and QA.

Requires CREDENTIAL_ENCRYPTION_KEY to be set in your environment.
The key must be a valid Fernet key (base64-encoded 32 bytes).

To generate a new key (do this once per environment, then store it):
    python scripts/cred.py genkey

Usage:
    python scripts/cred.py encrypt "my-api-token"
    python scripts/cred.py decrypt "gAAAAAB..."
    python scripts/cred.py genkey
"""

import os
import sys


def main():
    if len(sys.argv) < 2:
        print(__doc__)
        sys.exit(1)

    command = sys.argv[1]

    if command == "genkey":
        from cryptography.fernet import Fernet
        key = Fernet.generate_key().decode()
        print(key)
        print("\nAdd this to your .env.local:")
        print(f"CREDENTIAL_ENCRYPTION_KEY={key}")
        return

    key = os.environ.get("CREDENTIAL_ENCRYPTION_KEY")
    if not key:
        print("Error: CREDENTIAL_ENCRYPTION_KEY is not set.")
        print("Run 'python scripts/cred.py genkey' to generate one.")
        sys.exit(1)

    from cryptography.fernet import Fernet, InvalidToken
    f = Fernet(key)

    if command == "encrypt":
        if len(sys.argv) < 3:
            print("Usage: python scripts/cred.py encrypt <plaintext>")
            sys.exit(1)
        plaintext = sys.argv[2]
        print(f.encrypt(plaintext.encode()).decode())

    elif command == "decrypt":
        if len(sys.argv) < 3:
            print("Usage: python scripts/cred.py decrypt <ciphertext>")
            sys.exit(1)
        ciphertext = sys.argv[2]
        try:
            print(f.decrypt(ciphertext.encode()).decode())
        except InvalidToken:
            print("Error: decryption failed — wrong key or corrupted ciphertext.")
            sys.exit(1)

    else:
        print(f"Unknown command: {command!r}")
        print("Commands: encrypt, decrypt, genkey")
        sys.exit(1)


if __name__ == "__main__":
    main()
