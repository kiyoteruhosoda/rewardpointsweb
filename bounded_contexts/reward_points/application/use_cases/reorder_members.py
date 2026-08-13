"""子の並び順を決める（親メンバー）。

ナビゲーションもダッシュボードも、家族の決めた順で子を並べる。並びは家族に
1 つで、誰が見ても同じ順に出る（人ごとに持つと「上から 2 番目の子」が会話で
通じなくなる）。

並べ替えは順番を入れ替えるだけで、参加者を増やしも減らしもしない。渡された
一覧が家族の子とちょうど一致しない場合は、画面が古い一覧を握っている合図
なので断る。
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
        # この入口は family:manage を要求する（router）ので、可否は立場だけで決まる
        return detail_of(family, viewer=viewer, memberships=self._overview.build(viewer, can_manage=True))

    def _require_same_children(self, *, family_id: int, membership_ids: Sequence[int]) -> None:
        members = self._memberships.list_for_family(family_id)
        orderable = [member.id for member in members if member.role.has_own_ledger]
        # 抜け・重複・他家族の混入は、どれもここで同時に落ちる
        if sorted(membership_ids) != sorted(orderable):
            raise InvalidMemberOrderError


__all__ = ["ReorderMembersUseCase"]
