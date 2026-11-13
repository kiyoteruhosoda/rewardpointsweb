"""Rewrite the family rules (a memo of agreements) (parent members; ADR-0027).

Parents (owner / parent) can write them. Unlike renaming or dissolving, this changes
neither the family's makeup nor any ledger, so fixing everyday rules does not require the owner.

Empty or whitespace-only input is treated the same as "clear" (the repository turns it into NULL),
so that no family is left "with rules" while nothing shows on screen.
"""

from __future__ import annotations

from bounded_contexts.reward_points.application.dto.family_dto import FamilyDetailDTO, detail_of
from bounded_contexts.reward_points.application.family_access_resolver import FamilyAccessResolver
from bounded_contexts.reward_points.application.family_overview_builder import FamilyOverviewBuilder
from bounded_contexts.reward_points.domain.exceptions import FamilyAccessDeniedError
from bounded_contexts.reward_points.domain.repositories.family_repository import IFamilyRepository
from bounded_contexts.reward_points.domain.services import family_access_policy


class EditFamilyRulesUseCase:
    def __init__(
        self,
        access: FamilyAccessResolver,
        families: IFamilyRepository,
        overview: FamilyOverviewBuilder,
    ) -> None:
        self._access = access
        self._families = families
        self._overview = overview

    def execute(self, *, family_id: int, account_id: int, rules: str | None) -> FamilyDetailDTO:
        viewer = self._access.membership_in(family_id=family_id, account_id=account_id)
        if not family_access_policy.can_edit_family_rules(viewer):
            raise FamilyAccessDeniedError
        family = self._families.update_rules(family_id=family_id, rules=rules)
        # This entry point requires family:manage (router), so permission depends only on the role
        return detail_of(family, viewer=viewer, memberships=self._overview.build(viewer, can_manage=True))


__all__ = ["EditFamilyRulesUseCase"]
