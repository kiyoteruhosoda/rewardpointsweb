"""List of the families the signed-in account belongs to.

An account can belong to at most one family, so this is usually 0 or 1 items
(ADR-0013). The shape stays a list so that leftover past data with several
entries does not break it.
"""

from __future__ import annotations

from bounded_contexts.reward_points.application.dto.family_dto import FamilySummaryDTO
from bounded_contexts.reward_points.domain.repositories.family_membership_repository import (
    IFamilyMembershipRepository,
)
from bounded_contexts.reward_points.domain.repositories.family_repository import IFamilyRepository


class ListFamiliesUseCase:
    def __init__(self, families: IFamilyRepository, memberships: IFamilyMembershipRepository) -> None:
        self._families = families
        self._memberships = memberships

    def execute(self, account_id: int) -> list[FamilySummaryDTO]:
        mine = self._memberships.list_for_account(account_id)
        families = {family.id: family for family in self._families.list_by_ids([m.family_id for m in mine])}
        summaries: list[FamilySummaryDTO] = []
        for membership in mine:
            family = families.get(membership.family_id)
            if family is None:  # Safety net for a membership whose family is gone
                continue
            summaries.append(
                FamilySummaryDTO(
                    id=family.id,
                    name=family.name_value,
                    my_membership_id=membership.id,
                    my_role=membership.role,
                    # Display devices are not people, so they are not counted (ADR-0047)
                    member_count=sum(
                        1 for member in self._memberships.list_for_family(family.id) if not member.role.is_display
                    ),
                )
            )
        return summaries


__all__ = ["ListFamiliesUseCase"]
