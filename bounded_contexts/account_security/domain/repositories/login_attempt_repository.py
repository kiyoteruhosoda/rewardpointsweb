"""Persistence interface for failure records (implemented in the infrastructure layer).

It is not kept in process memory because Gunicorn runs with multiple workers
(attempts would be multiplied by the number of workers). Same reason as WebAuthn challenges (ADR-0055).
"""

from __future__ import annotations

from datetime import datetime
from typing import Protocol

from bounded_contexts.account_security.domain.entities.login_attempts import (
    LoginAttempts,
    ThrottlePolicy,
)


class LoginAttemptRepository(Protocol):
    def get(self, purpose: str, identifier: str) -> LoginAttempts:
        """Return the record. If none, return an empty record (0 failures)."""

    def save(self, attempts: LoginAttempts, now: datetime, policy: ThrottlePolicy) -> None:
        """Write the record. **Clean up rows that no longer matter at the same time** (there is no dedicated job)."""

    def forget(self, purpose: str, identifier: str) -> None:
        """Delete the record (on a correct entry)."""


__all__ = ["LoginAttemptRepository"]
