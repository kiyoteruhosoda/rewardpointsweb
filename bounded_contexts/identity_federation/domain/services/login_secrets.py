"""Generation of one-time values used in the login round trip, and their stored form.

``state`` / ``nonce`` / PKCE ``code_verifier`` / exchange tickets all have only one requirement,
"unguessable", so there is no reason to vary how they are generated. Keep it in one place.

An exchange ticket is a credential handed to its holder, so only its SHA-256 hash goes to the DB
(so that a leaked record cannot be used to sign in directly).
"""

from __future__ import annotations

import base64
import hashlib
import secrets

# 128 bits or more makes brute force impractical. RFC 7636 requires 43-128 characters for
# code_verifier, and 32 bytes in base64url (43 characters) meets that lower bound.
_TOKEN_BYTES = 32


def new_secret() -> str:
    """Make an unguessable URL-safe string (state / nonce / exchange ticket)."""
    return secrets.token_urlsafe(_TOKEN_BYTES)


def new_code_verifier() -> str:
    """PKCE ``code_verifier`` (RFC 7636)."""
    return secrets.token_urlsafe(_TOKEN_BYTES)


def code_challenge_of(code_verifier: str) -> str:
    """Make the ``S256`` ``code_challenge`` from a ``code_verifier``.

    ``plain`` is not used: anyone who can see the authorization request would get the verifier as is,
    defeating PKCE.
    """
    digest = hashlib.sha256(code_verifier.encode("ascii")).digest()
    return base64.urlsafe_b64encode(digest).decode("ascii").rstrip("=")


def hash_secret(value: str) -> str:
    """Hash for storage. Matching is always done hash to hash."""
    return hashlib.sha256(value.encode()).hexdigest()


__all__ = ["code_challenge_of", "hash_secret", "new_code_verifier", "new_secret"]
