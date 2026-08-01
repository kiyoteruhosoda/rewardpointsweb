"""家族・台帳へのアクセスを解決する入口。

すべてのユースケースは、対象を触る前にここを通す。判定そのものはドメインの
:mod:`~bounded_contexts.reward_points.domain.services.family_access_policy` が持ち、
ここは「読み込んで、判定させて、足りなければ例外にする」までを受け持つ。

所属していない家族・見えない台帳には **404** を返す（403 だと「その ID は存在
する」ことが分かってしまう）。所属はしているが立場が足りない場合だけ
``family_access_denied`` になる。
"""

from __future__ import annotations

from dataclasses import dataclass

from bounded_contexts.reward_points.domain.entities.family_membership import FamilyMembership
from bounded_contexts.reward_points.domain.entities.point_ledger import PointLedger
from bounded_contexts.reward_points.domain.exceptions import (
    FamilyAccessDeniedError,
    FamilyNotFoundError,
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
            raise FamilyNotFoundError
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
        if membership is None or not family_access_policy.can_view_ledger(membership, ledger):
            raise LedgerNotFoundError
        return LedgerAccess(membership=membership, ledger=ledger)

    def modifiable_ledger(self, *, ledger_id: int, account_id: int) -> LedgerAccess:
        access = self.viewable_ledger(ledger_id=ledger_id, account_id=account_id)
        if not family_access_policy.can_modify_ledger(access.membership, access.ledger):
            raise FamilyAccessDeniedError
        return access


__all__ = ["FamilyAccessResolver", "LedgerAccess"]
