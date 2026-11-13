"""Persistence interface for TOTP secrets (implemented in the infrastructure layer)."""

from __future__ import annotations

from datetime import datetime
from typing import Protocol

from bounded_contexts.account_security.domain.entities.totp_secret import TotpSecret


class TotpSecretRepository(Protocol):
    def find_by_user(self, user_id: int) -> TotpSecret | None:
        """Return the secret of *user_id* (``None`` if not enrolled)."""

    def save(self, secret: TotpSecret) -> TotpSecret:
        """Save as new or overwrite."""

    def confirm(self, user_id: int, confirmed_at: datetime) -> TotpSecret:
        """Mark the enrollment as confirmed (two-factor authentication becomes enabled)."""

    def delete(self, user_id: int) -> None:
        """Delete the secret (disables two-factor authentication)."""


__all__ = ["TotpSecretRepository"]
