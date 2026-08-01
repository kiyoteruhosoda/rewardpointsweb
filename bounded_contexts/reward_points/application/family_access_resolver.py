"""家族・台帳へのアクセスを解決する入口。

すべてのユースケースは、対象を触る前にここを通す。判定そのものはドメインの
:mod:`~bounded_contexts.reward_points.domain.services.family_access_policy` が持ち、
ここは「読み込んで、判定させて、足りなければ例外にする」までを受け持つ。

届かないときは **403**（``family_access_denied``）で揃える。「所属していない」
「立場が足りない」「他家族のものだった」を呼び出し元から区別させない。

存在しない家族 ID でも同じ 403 になる（参加が引けない、という同じ結末を辿る）
ため、この応答から家族の実在は分からない。台帳だけは、そもそも行が無い場合に
404（``ledger_not_found``）を返す — 存在しないものを「権限が無い」と言う方が
誤解を招くため。
"""

from __future__ import annotations

from dataclasses import dataclass

from bounded_contexts.reward_points.domain.entities.family_membership import FamilyMembership
from bounded_contexts.reward_points.domain.entities.point_ledger import PointLedger
from bounded_contexts.reward_points.domain.exceptions import (
    FamilyAccessDeniedError,
    LedgerNotFoundError,
)
from bounded_contexts.reward_points.domain.repositories.family_membership_repository import (
    IFamilyMembershipRepository,
)
from bounded_contexts.reward_points.domain.repositories.point_ledger_repository import IPointLedgerRepository
from bounded_contexts.reward_points.domain.services import family_access_policy


@dataclass(frozen=True, kw_only=True)
class LedgerAccess:
    """台帳と、そこへ届いた参加者。"""

    membership: FamilyMembership
    ledger: PointLedger


class FamilyAccessResolver:
    def __init__(self, memberships: IFamilyMembershipRepository, ledgers: IPointLedgerRepository) -> None:
        self._memberships = memberships
        self._ledgers = ledgers

    def membership_in(self, *, family_id: int, account_id: int) -> FamilyMembership:
        membership = self._memberships.find_in_family(family_id=family_id, account_id=account_id)
        if membership is None:
            raise FamilyAccessDeniedError
        return membership

    def require_guardian(self, *, family_id: int, account_id: int) -> FamilyMembership:
        membership = self.membership_in(family_id=family_id, account_id=account_id)
        if not family_access_policy.can_create_child(membership):
            raise FamilyAccessDeniedError
        return membership

    def require_owner(self, *, family_id: int, account_id: int) -> FamilyMembership:
        membership = self.membership_in(family_id=family_id, account_id=account_id)
        if not family_access_policy.can_administer_family(membership):
            raise FamilyAccessDeniedError
        return membership

    def viewable_ledger(self, *, ledger_id: int, account_id: int) -> LedgerAccess:
        ledger = self._ledgers.find_by_id(ledger_id)
        if ledger is None:
            raise LedgerNotFoundError
        membership = self._memberships.find_in_family(family_id=ledger.family_id, account_id=account_id)
        # 兄弟の台帳・他家族の台帳は、どちらもここで止まる（ADR-0009）
        if membership is None or not family_access_policy.can_view_ledger(membership, ledger):
            raise FamilyAccessDeniedError
        return LedgerAccess(membership=membership, ledger=ledger)

    def modifiable_ledger(self, *, ledger_id: int, account_id: int) -> LedgerAccess:
        access = self.viewable_ledger(ledger_id=ledger_id, account_id=account_id)
        if not family_access_policy.can_modify_ledger(access.membership, access.ledger):
            raise FamilyAccessDeniedError
        return access


__all__ = ["FamilyAccessResolver", "LedgerAccess"]
