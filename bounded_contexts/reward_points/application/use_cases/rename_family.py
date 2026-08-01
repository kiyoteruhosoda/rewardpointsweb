"""家族名を変える（owner のみ。ADR-0013）。"""

from __future__ import annotations

from bounded_contexts.reward_points.application.dto.family_dto import FamilyDetailDTO
from bounded_contexts.reward_points.application.family_access_resolver import FamilyAccessResolver
from bounded_contexts.reward_points.application.family_overview_builder import FamilyOverviewBuilder
from bounded_contexts.reward_points.domain.repositories.family_repository import IFamilyRepository


class RenameFamilyUseCase:
    def __init__(
        self,
        access: FamilyAccessResolver,
        families: IFamilyRepository,
        overview: FamilyOverviewBuilder,
    ) -> None:
        self._access = access
        self._families = families
        self._overview = overview

    def execute(self, *, family_id: int, account_id: int, name: str) -> FamilyDetailDTO:
        viewer = self._access.require_owner(family_id=family_id, account_id=account_id)
        family = self._families.update_name(family_id=family_id, name=name)
        return FamilyDetailDTO(
            id=family.id,
            name=family.name_value,
            my_membership_id=viewer.id,
            my_role=viewer.role,
            memberships=self._overview.build(viewer),
        )


__all__ = ["RenameFamilyUseCase"]
