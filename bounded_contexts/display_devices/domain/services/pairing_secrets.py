"""Generating the values used in pairing, and how they are stored (ADR-0047).

- Confirmation code (``user_code``): read and typed by people. 8 uppercase letters
  and digits, excluding confusable ones (0/O, 1/I/L), shown as two groups of 4 split by ``-``
- Device secret (``device_code``) and device credential (``device_credential``): the
  only requirement is that they cannot be guessed. 32 random bytes

All of these are credentials handed to their holder, so only SHA-256 hashes go into the DB.
"""

from __future__ import annotations

import hashlib
import secrets

USER_CODE_ALPHABET = "ABCDEFGHJKMNPQRSTUVWXYZ23456789"
USER_CODE_LENGTH = 8
_USER_CODE_GROUP = 4
_SECRET_BYTES = 32


def new_user_code() -> str:
    """A confirmation code (8 characters, no separator). Pass it through :func:`format_user_code` to display."""
    return "".join(secrets.choice(USER_CODE_ALPHABET) for _ in range(USER_CODE_LENGTH))


def format_user_code(code: str) -> str:
    """``KQ7M3XPA`` → ``KQ7M-3XPA``。"""
    return f"{code[:_USER_CODE_GROUP]}-{code[_USER_CODE_GROUP:]}"


def normalize_user_code(raw: str) -> str | None:
    """Normalize a typed confirmation code to the stored form (uppercase, no separator).

    Separators, spaces and lowercase are allowed. Returns ``None`` if it contains
    unused characters or has the wrong length (it cannot exist, no lookup needed).
    """
    code = "".join(ch for ch in raw.upper() if ch.isalnum())
    if len(code) != USER_CODE_LENGTH or any(ch not in USER_CODE_ALPHABET for ch in code):
        return None
    return code


def new_secret() -> str:
    """A device secret or device credential."""
    return secrets.token_urlsafe(_SECRET_BYTES)


def hash_secret(value: str) -> str:
    """Hash for storage. Comparisons are always hash to hash."""
    return hashlib.sha256(value.encode()).hexdigest()


__all__ = [
    "USER_CODE_ALPHABET",
    "USER_CODE_LENGTH",
    "format_user_code",
    "hash_secret",
    "new_secret",
    "new_user_code",
    "normalize_user_code",
]
