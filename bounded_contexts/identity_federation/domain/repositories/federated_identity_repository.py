"""Persistence interface for links to IdP accounts (implemented in the Infrastructure layer)."""

from __future__ import annotations

from collections.abc import Sequence
from typing import Protocol

from bounded_contexts.identity_federation.domain.entities.federated_identity import (
    FederatedIdentity,
)


class FederatedIdentityRepository(Protocol):
    def find(self, issuer: str, subject: str) -> FederatedIdentity | None:
        """Look up a link. ``None`` if absent."""

    def link(self, identity: FederatedIdentity) -> FederatedIdentity:
        """Save a link (an existing ``(issuer, subject)`` is not overwritten)."""

    def find_for_user(self, issuer: str, user_id: int) -> FederatedIdentity | None:
        """Look up whether the user is linked to the IdP (ADR-0036)."""

    def unlink(self, identity: FederatedIdentity) -> None:
        """Delete a link. **Does not touch the user itself.**"""

    def touch(self, identity: FederatedIdentity) -> None:
        """Update the last login time (for inventory; not used for authorization)."""

    def list_for_issuer(self, issuer: str) -> Sequence[FederatedIdentity]:
        """Return all users linked to the IdP (periodic reconciliation; ADR-0040).

        ⚠ **No paging.** Reconciliation means "ask about every `sub` we hold", so cutting it
        short would **leave the cut-off part unchecked every time**.
        """


__all__ = ["FederatedIdentityRepository"]
