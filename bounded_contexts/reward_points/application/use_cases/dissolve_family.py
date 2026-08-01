"""家族を解散する（owner のみ。ADR-0013）。

解散できるのは自分以外の参加者がいない場合だけ。親も子も、誰かが残っている
うちは解散できない — 台帳ごと黙って消える経路を作らない（ADR-0010）。子の
参加は、台帳が空であれば除名（``RemoveMembershipUseCase``）で先に外せる。

未使用の招待は家族と一緒に消える（外部キーの CASCADE）。
"""

from __future__ import annotations

from bounded_contexts.reward_points.application.family_access_resolver import FamilyAccessResolver
from bounded_contexts.reward_points.domain.exceptions import FamilyNotEmptyError
from bounded_contexts.reward_points.domain.repositories.family_membership_repository import (
    IFamilyMembershipRepository,
)
from bounded_contexts.reward_points.domain.repositories.family_repository import IFamilyRepository


class DissolveFamilyUseCase:
    def __init__(
        self,
        access: FamilyAccessResolver,
        families: IFamilyRepository,
        memberships: IFamilyMembershipRepository,
    ) -> None:
        self._access = access
        self._families = families
        self._memberships = memberships

    def execute(self, *, family_id: int, account_id: int) -> None:
        owner = self._access.require_owner(family_id=family_id, account_id=account_id)
        others = [m for m in self._memberships.list_for_family(family_id) if m.id != owner.id]
        if others:
            raise FamilyNotEmptyError
        # CASCADE に頼らず自分の参加も明示的に消す（開発用 SQLite は外部キーを
        # 検査しない設定で動くことがあり、残骸が残るため）
        self._memberships.delete(owner.id)
        self._families.delete(family_id)


__all__ = ["DissolveFamilyUseCase"]
