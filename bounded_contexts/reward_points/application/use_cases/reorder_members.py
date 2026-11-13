"""Set the order of children (parent members).

Navigation and the dashboard both list children in the family's chosen order.
There is one order per family and everyone sees the same one (per-person orders
would make "the second child from the top" meaningless in conversation).

Reordering only swaps positions; it never adds or removes members. If the given
list does not exactly match the family's children, the screen is holding a stale
list, so we refuse.
"""

from __future__ import annotations

from collections.abc import Sequence

from bounded_contexts.reward_points.application.dto.family_dto import FamilyDetailDTO, detail_of
from bounded_contexts.reward_points.application.family_access_resolver import FamilyAccessResolver
from bounded_contexts.reward_points.application.family_overview_builder import FamilyOverviewBuilder
from bounded_contexts.reward_points.domain.exceptions import (
    FamilyAccessDeniedError,
    FamilyNotFoundError,
    InvalidMemberOrderError,
)
from bounded_contexts.reward_points.domain.repositories.family_membership_repository import (
    IFamilyMembershipRepository,
)
from bounded_contexts.reward_points.domain.repositories.family_repository import IFamilyRepository
from bounded_contexts.reward_points.domain.services import family_access_policy


class ReorderMembersUseCase:
    def __init__(
        self,
        *,
        access: FamilyAccessResolver,
        memberships: IFamilyMembershipRepository,
        families: IFamilyRepository,
        overview: FamilyOverviewBuilder,
    ) -> None:
        self._access = access
        self._memberships = memberships
        self._families = families
        self._overview = overview

    def execute(self, *, family_id: int, account_id: int, membership_ids: Sequence[int]) -> FamilyDetailDTO:
        viewer = self._access.membership_in(family_id=family_id, account_id=account_id)
        if not family_access_policy.can_reorder_members(viewer):
            raise FamilyAccessDeniedError
        self._require_same_children(family_id=family_id, membership_ids=membership_ids)
        self._memberships.reorder(family_id=family_id, membership_ids=membership_ids)

        family = self._families.find_by_id(family_id)
        if family is None:
            raise FamilyNotFoundError
        # This entry point requires family:manage (router), so permission depends on role alone
        return detail_of(family, viewer=viewer, memberships=self._overview.build(viewer, can_manage=True))

    def _require_same_children(self, *, family_id: int, membership_ids: Sequence[int]) -> None:
        members = self._memberships.list_for_family(family_id)
        orderable = [member.id for member in members if member.role.has_own_ledger]
        # Missing, duplicate, or other-family IDs all fail here at once
        if sorted(membership_ids) != sorted(orderable):
            raise InvalidMemberOrderError


__all__ = ["ReorderMembersUseCase"]
