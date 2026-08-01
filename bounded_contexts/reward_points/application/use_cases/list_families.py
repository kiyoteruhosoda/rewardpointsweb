"""ログイン中のアカウントが所属する家族の一覧。

1 つのアカウントが複数の家族に所属することを許す（別居親・再婚等。ADR-0009）。
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
            if family is None:  # 参加は残っているのに家族が消えている場合の保険
                continue
            summaries.append(
                FamilySummaryDTO(
                    id=family.id,
                    name=family.name_value,
                    my_membership_id=membership.id,
                    my_role=membership.role,
                    member_count=len(self._memberships.list_for_family(family.id)),
                )
            )
        return summaries


__all__ = ["ListFamiliesUseCase"]
