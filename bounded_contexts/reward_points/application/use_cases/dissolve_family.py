"""Dissolve a family (owner only; ADR-0013).

Only possible when there are no members other than the owner. While anyone,
parent or child, remains, the family cannot be dissolved; there must be no path
that silently deletes ledgers along with it (ADR-0010). A child's membership
can be removed first (``RemoveMembershipUseCase``) if its ledger is empty.

Unused invitations go with the family (foreign key CASCADE).
"""

from __future__ import annotations

from bounded_contexts.reward_points.application.family_access_resolver import FamilyAccessResolver
from bounded_contexts.reward_points.domain.exceptions import FamilyNotEmptyError
from bounded_contexts.reward_points.domain.repositories.family_membership_repository import (
    IFamilyMembershipRepository,
)
from bounded_contexts.reward_points.domain.repositories.family_repository import IFamilyRepository


class DissolveFamilyUseCase:
    def __init__(
        self,
        access: FamilyAccessResolver,
        families: IFamilyRepository,
        memberships: IFamilyMembershipRepository,
    ) -> None:
        self._access = access
        self._families = families
        self._memberships = memberships

    def execute(self, *, family_id: int, account_id: int) -> None:
        owner = self._access.require_owner(family_id=family_id, account_id=account_id)
        others = [m for m in self._memberships.list_for_family(family_id) if m.id != owner.id]
        if others:
            raise FamilyNotEmptyError
        # Delete our own membership explicitly instead of relying on CASCADE (the dev
        # SQLite may run without foreign key checks, which would leave leftovers)
        self._memberships.delete(owner.id)
        self._families.delete(family_id)


__all__ = ["DissolveFamilyUseCase"]
