"""家族の詳細（参加者と、見える範囲の台帳・残高）。

``can_manage`` は呼び出し元が ``family:manage`` を持つか。参加者ごとの操作の
可否（``can_*``）を組み立てるのに要る（ADR-0019）。
"""

from __future__ import annotations

from bounded_contexts.reward_points.application.dto.family_dto import FamilyDetailDTO, detail_of
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

    def execute(self, *, family_id: int, account_id: int, can_manage: bool) -> FamilyDetailDTO:
        viewer = self._access.membership_in(family_id=family_id, account_id=account_id)
        family = self._families.find_by_id(family_id)
        if family is None:
            raise FamilyNotFoundError
        return detail_of(family, viewer=viewer, memberships=self._overview.build(viewer, can_manage=can_manage))


__all__ = ["ViewFamilyUseCase"]
