"""家族から自分の意思で抜ける（脱退。ADR-0013）。

抜けられるのは親（owner / parent）だけで、他に**アカウントの結び付いた**親が
残る場合に限る。子（ゲスト）は自分では抜けられない。owner が抜けるときは、
最も古くから居る parent が owner を引き継ぐ — 家族は管理できる人を失わない。

親の participation はアカウントが消えると未紐付けのまま残る
（``account_id`` の ``SET NULL``）。誰もログインできない参加者は「残る親」にも
引き継ぎ先にも数えない — 数えると、owner の脱退が管理者不在の家族を作ってしまう。

抜けた後は初期状態と同じ（どの家族にも所属していない）。台帳の記録は家族に
残るが、操作者への参照は外れる（``granted_by_membership_id`` は ``SET NULL``）。
"""

from __future__ import annotations

from bounded_contexts.reward_points.application.family_access_resolver import FamilyAccessResolver
from bounded_contexts.reward_points.domain.entities.family_membership import FamilyMembership
from bounded_contexts.reward_points.domain.exceptions import (
    ChildCannotLeaveFamilyError,
    LastGuardianCannotLeaveError,
)
from bounded_contexts.reward_points.domain.repositories.family_membership_repository import (
    IFamilyMembershipRepository,
)
from bounded_contexts.reward_points.domain.value_objects.family_role import FamilyRole


class LeaveFamilyUseCase:
    def __init__(self, access: FamilyAccessResolver, memberships: IFamilyMembershipRepository) -> None:
        self._access = access
        self._memberships = memberships

    def execute(self, *, family_id: int, account_id: int) -> None:
        me = self._access.membership_in(family_id=family_id, account_id=account_id)
        if me.role.has_own_ledger:
            raise ChildCannotLeaveFamilyError
        remaining = [m for m in self._memberships.list_for_family(family_id) if m.id != me.id]
        guardians = [m for m in remaining if m.role.is_guardian and m.is_linked]
        if not guardians:
            raise LastGuardianCannotLeaveError
        if me.role.can_administer_family:
            self._memberships.update_role(membership_id=_successor(guardians).id, role=FamilyRole.OWNER)
        self._memberships.delete(me.id)


def _successor(guardians: list[FamilyMembership]) -> FamilyMembership:
    """owner を引き継ぐ parent。最も古い参加者（同時なら ID の小さい方）。"""
    return min(guardians, key=lambda m: (m.created_at, m.id))


__all__ = ["LeaveFamilyUseCase"]
