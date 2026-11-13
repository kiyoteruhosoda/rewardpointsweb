"""Unlinking -- the user removes their own link to an IdP (ADR-0036).

⚠ **Do not create users who can no longer sign in after removal.** Removing the IdP from someone with neither a local
password nor a passkey leaves recovery by an administrator as the only option. Whether an entrance
remains is **counted and passed in by the caller** -- second factors are held by another
context (``account_security``), and we do not reach across the boundary to look them up
(same construction as ADR-0035).
"""

from __future__ import annotations

from dataclasses import dataclass

from bounded_contexts.identity_federation.domain.exceptions import (
    SsoIdentityNotLinkedError,
    SsoLastEntranceError,
)
from bounded_contexts.identity_federation.domain.repositories.federated_identity_repository import (
    FederatedIdentityRepository,
)


@dataclass(frozen=True)
class UnlinkFederatedIdentity:
    identities: FederatedIdentityRepository

    def execute(self, *, issuer: str, user_id: int, has_other_entrance: bool) -> None:
        identity = self.identities.find_for_user(issuer, user_id)
        if identity is None:
            raise SsoIdentityNotLinkedError
        if not has_other_entrance:
            raise SsoLastEntranceError
        self.identities.unlink(identity)


__all__ = ["UnlinkFederatedIdentity"]
