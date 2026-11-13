"""Persistence interface for revocation records (implemented in the Infrastructure layer)."""

from __future__ import annotations

from typing import Protocol

from bounded_contexts.identity_federation.domain.entities.session_revocation import (
    SessionRevocation,
)
from bounded_contexts.identity_federation.domain.value_objects.federated_login import (
    FederatedLogin,
)


class SessionRevocationRepository(Protocol):
    def record(self, revocation: SessionRevocation) -> bool:
        """Keep a record. **If the same ``jti`` already exists, do nothing and return ``False``**.

        The ADR-0024 sender uses the same ``jti`` for every resend, so this is where duplicate
        deliveries are absorbed. Expired records are cleaned up at this opportunity.
        """

    def is_revoked(self, login: FederatedLogin) -> bool:
        """Whether the login matches any of the received revocations."""


__all__ = ["SessionRevocationRepository"]
