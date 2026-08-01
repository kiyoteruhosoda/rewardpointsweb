"""家族の詳細（参加者と、見える範囲の台帳・残高）。"""

from __future__ import annotations

from bounded_contexts.reward_points.application.dto.family_dto import FamilyDetailDTO
from bounded_contexts.reward_points.application.family_access_resolver import FamilyAccessResolver
from bounded_contexts.reward_points.application.family_overview_builder import FamilyOverviewBuilder
from bounded_contexts.reward_points.domain.exceptions import FamilyNotFoundError
from bounded_contexts.reward_points.domain.repositories.family_repository import IFamilyRepository


class ViewFamilyUseCase:
    def __init__(
        self,
        access: FamilyAccessResolver,
        families: IFamilyRepository,
        overview: FamilyOverviewBuilder,
    ) -> None:
        self._access = access
        self._families = families
        self._overview = overview

    def execute(self, *, family_id: int, account_id: int) -> FamilyDetailDTO:
        viewer = self._access.membership_in(family_id=family_id, account_id=account_id)
        family = self._families.find_by_id(family_id)
        if family is None:
            raise FamilyNotFoundError
        return FamilyDetailDTO(
            id=family.id,
            name=family.name_value,
            my_membership_id=viewer.id,
            my_role=viewer.role,
            memberships=self._overview.build(viewer),
        )


__all__ = ["ViewFamilyUseCase"]
