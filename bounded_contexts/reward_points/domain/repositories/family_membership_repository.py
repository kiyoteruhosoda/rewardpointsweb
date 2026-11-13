"""Persistence interface for family memberships."""

from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import Sequence
from datetime import datetime

from bounded_contexts.reward_points.domain.entities.family_membership import FamilyMembership
from bounded_contexts.reward_points.domain.value_objects.family_role import FamilyRole


class IFamilyMembershipRepository(ABC):
    @abstractmethod
    def add(
        self,
        *,
        family_id: int,
        account_id: int | None,
        role: FamilyRole,
        display_name: str,
    ) -> FamilyMembership: ...

    @abstractmethod
    def find_by_id(self, membership_id: int) -> FamilyMembership | None: ...

    @abstractmethod
    def find_in_family(self, *, family_id: int, account_id: int) -> FamilyMembership | None:
        """Look up the caller's role in that family (the starting point of authorization)."""

    @abstractmethod
    def list_for_family(self, family_id: int) -> list[FamilyMembership]: ...

    @abstractmethod
    def list_for_account(self, account_id: int) -> list[FamilyMembership]:
        """Memberships of *account_id*. At most one family, so usually 0 or 1 items (ADR-0013)."""

    @abstractmethod
    def link_account(self, *, membership_id: int, account_id: int) -> FamilyMembership:
        """Link the account when an invitation is accepted."""

    @abstractmethod
    def delete(self, membership_id: int) -> None: ...

    @abstractmethod
    def update_display_name(self, *, membership_id: int, display_name: str) -> FamilyMembership: ...

    @abstractmethod
    def update_role(self, *, membership_id: int, role: FamilyRole) -> FamilyMembership:
        """Change the role (handover when the owner leaves; ADR-0013)."""

    @abstractmethod
    def propose_independence(self, *, membership_id: int, proposed_at: datetime) -> FamilyMembership:
        """Record an independence proposal (ADR-0014). The child stays a member until they approve."""

    @abstractmethod
    def clear_independence_proposal(self, membership_id: int) -> FamilyMembership:
        """Withdraw an independence proposal (ADR-0014)."""

    @abstractmethod
    def reorder(self, *, family_id: int, membership_ids: Sequence[int]) -> None:
        """Renumber the sort order to the given order (the first one is 0).

        The implementation sets the whole list's order at once, so the caller
        passes only the sequence of IDs.
        """

    @abstractmethod
    def list_by_ids(self, membership_ids: Sequence[int]) -> list[FamilyMembership]: ...

    @abstractmethod
    def list_displays(self) -> list[FamilyMembership]:
        """Display devices of all families (ADR-0047). Used for the operator's list."""


__all__ = ["IFamilyMembershipRepository"]
