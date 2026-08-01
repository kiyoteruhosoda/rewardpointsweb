"""子（ゲスト）が独立を承認し、独立が成立する（ADR-0014）。

承認できるのは、親メンバーから独立を指示されている子本人だけ。成立すると

- 参加・台帳・全ての記録を家族から削除する（追記専用 — ADR-0010 — の
  明示的な例外。独立は儀式であり、黙って消える経路ではない）
- アカウントは残り、どの家族にも所属しない初期状態になる
- 親（メンバー）と同じアプリケーションロールへ昇格し、自分の家族を作ることも
  招待をメンバーとして受けることもできるようになる
"""

from __future__ import annotations

from bounded_contexts.reward_points.application.family_access_resolver import FamilyAccessResolver
from bounded_contexts.reward_points.domain.exceptions import (
    FamilyAccessDeniedError,
    IndependenceNotProposedError,
)
from bounded_contexts.reward_points.domain.repositories.account_directory import IAccountProvisioning
from bounded_contexts.reward_points.domain.repositories.family_membership_repository import (
    IFamilyMembershipRepository,
)
from bounded_contexts.reward_points.domain.repositories.point_ledger_repository import IPointLedgerRepository
from bounded_contexts.reward_points.domain.repositories.point_transaction_repository import (
    IPointTransactionRepository,
)


class ApproveIndependenceUseCase:
    def __init__(
        self,
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

    def execute(self, *, family_id: int, account_id: int) -> None:
        me = self._access.membership_in(family_id=family_id, account_id=account_id)
        if not me.role.has_own_ledger:
            # 親には独立は無い。家族を離れたい親は脱退（leave）を使う
            raise FamilyAccessDeniedError
        if not me.independence_proposed:
            raise IndependenceNotProposedError
        self._remove_ledger_with_records(me.id)
        self._memberships.delete(me.id)
        self._provisioning.grant_guardian_permissions(account_id)

    def _remove_ledger_with_records(self, membership_id: int) -> None:
        ledger = self._ledgers.find_by_membership(membership_id)
        if ledger is None:
            return
        self._transactions.delete_by_ledger(ledger.id)
        self._ledgers.delete(ledger.id)


__all__ = ["ApproveIndependenceUseCase"]
