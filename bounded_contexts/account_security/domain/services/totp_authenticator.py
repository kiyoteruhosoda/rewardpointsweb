"""Interface for TOTP generation and verification (implemented in the infrastructure layer).

The RFC 6238 computation itself is left to a library. The domain knows only three things:
"create a shared key", "build the URI passed to the authenticator app", and "verify a code".
"""

from __future__ import annotations

from typing import Protocol


class TotpAuthenticator(Protocol):
    def generate_secret(self) -> str:
        """Issue a new shared key (Base32)."""

    def provisioning_uri(self, *, secret: str, account_name: str) -> str:
        """Build the ``otpauth://`` URI read by the authenticator app."""

    def verify(self, *, secret: str, code: str) -> bool:
        """Decide whether a one-time code is correct (the allowed clock drift is an implementation setting)."""


__all__ = ["TotpAuthenticator"]
