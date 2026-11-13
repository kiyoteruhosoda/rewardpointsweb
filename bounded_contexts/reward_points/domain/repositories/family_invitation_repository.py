"""Persistence interface for invitations.

Hashing the code stays inside this port's implementation (Infrastructure). The
domain handles only the plaintext code and does not know the storage format.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import datetime

from bounded_contexts.reward_points.domain.entities.family_invitation import FamilyInvitation
from bounded_contexts.reward_points.domain.value_objects.family_role import FamilyRole


@dataclass(frozen=True, kw_only=True)
class IssuedInvitation:
    """Result of issuing. The plaintext code can be retrieved only this once."""

    invitation: FamilyInvitation
    code: str


class IFamilyInvitationRepository(ABC):
    @abstractmethod
    def issue(
        self,
        *,
        family_id: int,
        role: FamilyRole,
        target_membership_id: int | None,
        expires_at: datetime,
    ) -> IssuedInvitation: ...

    @abstractmethod
    def find_by_code(self, code: str) -> FamilyInvitation | None: ...

    @abstractmethod
    def list_pending(self, family_id: int, *, now: datetime) -> list[FamilyInvitation]:
        """Only unused, unexpired ones."""

    @abstractmethod
    def find_in_family(self, *, family_id: int, invitation_id: int) -> FamilyInvitation | None: ...

    @abstractmethod
    def consume(self, code: str, *, now: datetime) -> FamilyInvitation | None:
        """Return the invitation **after marking it used**. ``None`` if it cannot be used.

        Splitting "load, then mark used" into two steps would let two concurrent
        requests with the same code both decide it is "still usable". This single
        step guarantees single use (the implementation relies on the row lock of a
        conditional UPDATE).
        """

    @abstractmethod
    def delete(self, invitation_id: int) -> None: ...


__all__ = ["IFamilyInvitationRepository", "IssuedInvitation"]
