"""参加者を家族から外す（owner のみ。表示端末だけは親なら外せる）。

台帳は追記専用で、消す手段を用意していない（ADR-0010）。記録が 1 件でも
残っている参加者は外せない — 外せてしまうと、履歴が黙って消える経路になる。

子アカウントは招待の受諾（redeem）で生まれ、家族の参加としてだけ存在するので、
除名ではアカウントごと削除する（ADR-0018）。結び付いた子のアカウントが redeem
由来であることは、accept が子の招待を断ること
（``child_invitation_requires_signup``）が保証する。親のアカウントは家族と
独立に存在する（管理者が作る）ため消さない。

表示端末（ADR-0047）は親（owner / parent）なら外せる。端末のアカウントも承認で
生まれ、その家族を映すためだけに在るので、参加と一緒に消す。
"""

from __future__ import annotations

from bounded_contexts.reward_points.application.family_access_resolver import FamilyAccessResolver
from bounded_contexts.reward_points.domain.entities.family_membership import FamilyMembership
from bounded_contexts.reward_points.domain.exceptions import (
    FamilyAccessDeniedError,
    LedgerNotEmptyError,
    MembershipNotFoundError,
)
from bounded_contexts.reward_points.domain.repositories.account_directory import IAccountProvisioning
from bounded_contexts.reward_points.domain.repositories.family_membership_repository import (
    IFamilyMembershipRepository,
)
from bounded_contexts.reward_points.domain.repositories.point_ledger_repository import IPointLedgerRepository
from bounded_contexts.reward_points.domain.repositories.point_transaction_repository import (
    IPointTransactionRepository,
)
from bounded_contexts.reward_points.domain.services import family_access_policy


class RemoveMembershipUseCase:
    def __init__(
        self,
        *,
        access: FamilyAccessResolver,
        memberships: IFamilyMembershipRepository,
        ledgers: IPointLedgerRepository,
        transactions: IPointTransactionRepository,
        provisioning: IAccountProvisioning,
    ) -> None:
        self._access = access
        self._memberships = memberships
        self._ledgers = ledgers
        self._transactions = transactions
        self._provisioning = provisioning

    def execute(self, *, family_id: int, membership_id: int, account_id: int) -> int | None:
        """外す。表示端末を外したときは、その端末のアカウント ID を返す（監査ログ用）。"""
        actor = self._access.membership_in(family_id=family_id, account_id=account_id)
        target = self._memberships.find_by_id(membership_id)
        if target is None or target.family_id != family_id:
            # 外せない立場の人には、相手の有無より先に 403 を返す（require_owner と同じ順）
            if not family_access_policy.can_administer_family(actor):
                raise FamilyAccessDeniedError
            raise MembershipNotFoundError
        if target.role.is_display:
            self._detach_display(actor, target)
            return target.account_id
        if not family_access_policy.can_administer_family(actor) or target.id == actor.id:
            # owner が自分を外すと家族を管理できる人がいなくなる
            raise FamilyAccessDeniedError
        self._remove_ledger_of(target.id)
        self._memberships.delete(target.id)
        self._delete_owned_account_of(target)
        return None

    def _detach_display(self, actor: FamilyMembership, target: FamilyMembership) -> None:
        if not family_access_policy.can_detach_display(actor, target):
            raise FamilyAccessDeniedError
        self._memberships.delete(target.id)
        self._delete_owned_account_of(target)

    def _delete_owned_account_of(self, target: FamilyMembership) -> None:
        """家族の参加としてだけ存在するアカウント（子・表示端末）を消す。"""
        owned = target.role.has_own_ledger or target.role.is_display
        if owned and target.account_id is not None:
            self._provisioning.delete_account(target.account_id)

    def _remove_ledger_of(self, membership_id: int) -> None:
        ledger = self._ledgers.find_by_membership(membership_id)
        if ledger is None:
            return
        if self._transactions.count_by_ledger(ledger.id) > 0:
            raise LedgerNotEmptyError
        self._ledgers.delete(ledger.id)


__all__ = ["RemoveMembershipUseCase"]
