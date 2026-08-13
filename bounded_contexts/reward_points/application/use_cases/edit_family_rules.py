"""家族のルール（約束ごとのメモ）を書き換える（親メンバー。ADR-0027）。

書けるのは親（owner / parent）。改名や解散と違って家族の構成も台帳も動かさない
ので、日々の決めごとを直すのに owner を呼ぶ形にはしない。

空文字・空白だけの入力は「消す」と同じに扱う（リポジトリが NULL へ寄せる）。
画面には何も出ないのに「ルールあり」の家族が残らないようにするため。
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
        # この入口は family:manage を要求する（router）ので、可否は立場だけで決まる
        return detail_of(family, viewer=viewer, memberships=self._overview.build(viewer, can_manage=True))


__all__ = ["EditFamilyRulesUseCase"]
