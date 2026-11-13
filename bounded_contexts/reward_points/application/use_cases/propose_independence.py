"""Propose that a child (guest) become independent (parent members; ADR-0014).

Independence takes two steps: a parent member proposes it and the child approves.
This use case is the first step. Proposing deletes nothing and can be revoked
until approved.

Only children linked to an account qualify. An unlinked child has no way to
approve (they cannot even log in), so use removal (``RemoveMembershipUseCase``).
"""

from __future__ import annotations

from bounded_contexts.reward_points.application.family_access_resolver import FamilyAccessResolver
from bounded_contexts.reward_points.domain.entities.family_membership import FamilyMembership
from bounded_contexts.reward_points.domain.exceptions import (
    ChildAccountRequiredError,
    MembershipNotFoundError,
    MembershipNotLinkedError,
)
from bounded_contexts.reward_points.domain.repositories.family_membership_repository import (
    IFamilyMembershipRepository,
)
from shared.kernel.timestamps import utcnow


class ProposeIndependenceUseCase:
    def __init__(self, access: FamilyAccessResolver, memberships: IFamilyMembershipRepository) -> None:
        self._access = access
        self._memberships = memberships

    def execute(self, *, family_id: int, membership_id: int, account_id: int) -> FamilyMembership:
        self._access.require_guardian(family_id=family_id, account_id=account_id)
        target = self._memberships.find_by_id(membership_id)
        if target is None or target.family_id != family_id:
            raise MembershipNotFoundError
        if not target.role.has_own_ledger:
            raise ChildAccountRequiredError
        if not target.is_linked:
            raise MembershipNotLinkedError
        return self._memberships.propose_independence(membership_id=target.id, proposed_at=utcnow())


class RevokeIndependenceProposalUseCase:
    """Revoke an independence proposal (parent members; any time before approval)."""

    def __init__(self, access: FamilyAccessResolver, memberships: IFamilyMembershipRepository) -> None:
        self._access = access
        self._memberships = memberships

    def execute(self, *, family_id: int, membership_id: int, account_id: int) -> None:
        self._access.require_guardian(family_id=family_id, account_id=account_id)
        target = self._memberships.find_by_id(membership_id)
        if target is None or target.family_id != family_id:
            raise MembershipNotFoundError
        self._memberships.clear_independence_proposal(target.id)


__all__ = ["ProposeIndependenceUseCase", "RevokeIndependenceProposalUseCase"]
