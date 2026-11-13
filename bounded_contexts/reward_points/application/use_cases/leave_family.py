"""Leave a family voluntarily (ADR-0013).

Only parents (owner / parent) can leave, and only when another parent **with a
linked account** remains. Children (guests) cannot leave by themselves. When the
owner leaves, the longest-standing parent takes over as owner, so the family
never loses someone who can manage it.

A parent's membership stays, unlinked, when its account is deleted
(``SET NULL`` on ``account_id``). A member nobody can sign in as is counted
neither as a "remaining parent" nor as a successor; counting it would let the
owner's leaving create a family with no manager.

After leaving, the account is back in the initial state (belongs to no family).
Ledger entries stay with the family, but the reference to the actor is cleared
(``granted_by_membership_id`` is ``SET NULL``).
"""

from __future__ import annotations

from bounded_contexts.reward_points.application.family_access_resolver import FamilyAccessResolver
from bounded_contexts.reward_points.domain.entities.family_membership import FamilyMembership
from bounded_contexts.reward_points.domain.exceptions import (
    ChildCannotLeaveFamilyError,
    FamilyAccessDeniedError,
    LastGuardianCannotLeaveError,
)
from bounded_contexts.reward_points.domain.repositories.family_membership_repository import (
    IFamilyMembershipRepository,
)
from bounded_contexts.reward_points.domain.value_objects.family_role import FamilyRole


class LeaveFamilyUseCase:
    def __init__(self, access: FamilyAccessResolver, memberships: IFamilyMembershipRepository) -> None:
        self._access = access
        self._memberships = memberships

    def execute(self, *, family_id: int, account_id: int) -> None:
        me = self._access.membership_in(family_id=family_id, account_id=account_id)
        if me.role.has_own_ledger:
            raise ChildCannotLeaveFamilyError
        if not me.role.is_guardian:
            # A display device does not leave by itself; a parent or an operator removes it (ADR-0047)
            raise FamilyAccessDeniedError
        remaining = [m for m in self._memberships.list_for_family(family_id) if m.id != me.id]
        guardians = [m for m in remaining if m.role.is_guardian and m.is_linked]
        if not guardians:
            raise LastGuardianCannotLeaveError
        if me.role.can_administer_family:
            self._memberships.update_role(membership_id=_successor(guardians).id, role=FamilyRole.OWNER)
        self._memberships.delete(me.id)


def _successor(guardians: list[FamilyMembership]) -> FamilyMembership:
    """The parent who takes over as owner: the oldest member (on a tie, the smaller ID)."""
    return min(guardians, key=lambda m: (m.created_at, m.id))


__all__ = ["LeaveFamilyUseCase"]
