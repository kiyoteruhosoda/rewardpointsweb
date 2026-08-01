"""参加者を家族から外す（owner のみ）。

台帳は追記専用で、消す手段を用意していない（ADR-0010）。記録が 1 件でも
残っている参加者は外せない — 外せてしまうと、履歴が黙って消える経路になる。
"""

from __future__ import annotations

from bounded_contexts.reward_points.application.family_access_resolver import FamilyAccessResolver
from bounded_contexts.reward_points.domain.exceptions import (
    FamilyAccessDeniedError,
    LedgerNotEmptyError,
    MembershipNotFoundError,
)
from bounded_contexts.reward_points.domain.repositories.family_membership_repository import (
    IFamilyMembershipRepository,
)
from bounded_contexts.reward_points.domain.repositories.point_ledger_repository import IPointLedgerRepository
from bounded_contexts.reward_points.domain.repositories.point_transaction_repository import (
    IPointTransactionRepository,
)


class RemoveMembershipUseCase:
    def __init__(
        self,
        access: FamilyAccessResolver,
        memberships: IFamilyMembershipRepository,
        ledgers: IPointLedgerRepository,
        transactions: IPointTransactionRepository,
    ) -> None:
        self._access = access
        self._memberships = memberships
        self._ledgers = ledgers
        self._transactions = transactions

    def execute(self, *, family_id: int, membership_id: int, account_id: int) -> None:
        owner = self._access.require_owner(family_id=family_id, account_id=account_id)
        target = self._memberships.find_by_id(membership_id)
        if target is None or target.family_id != family_id:
            raise MembershipNotFoundError
        if target.id == owner.id:
            # owner が自分を外すと家族を管理できる人がいなくなる
            raise FamilyAccessDeniedError
        self._remove_ledger_of(target.id)
        self._memberships.delete(target.id)

    def _remove_ledger_of(self, membership_id: int) -> None:
        ledger = self._ledgers.find_by_membership(membership_id)
        if ledger is None:
            return
        if self._transactions.count_by_ledger(ledger.id) > 0:
            raise LedgerNotEmptyError
        self._ledgers.delete(ledger.id)


__all__ = ["RemoveMembershipUseCase"]
