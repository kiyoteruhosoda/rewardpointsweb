"""台帳（残高と履歴）を見る。

残高は履歴の合計として毎回導出する（残高列は持たない。ADR-0010）。応答に
``can_modify`` を含めるので、画面側は「変更 UI を出すか」をこの 1 つの値で
決められる（立場の名前で分岐しない）。
"""

from __future__ import annotations

from bounded_contexts.reward_points.application.dto.ledger_dto import LedgerDTO, TransactionDTO
from bounded_contexts.reward_points.application.family_access_resolver import FamilyAccessResolver
from bounded_contexts.reward_points.domain.entities.point_transaction import PointTransaction
from bounded_contexts.reward_points.domain.exceptions import MembershipNotFoundError
from bounded_contexts.reward_points.domain.repositories.family_membership_repository import (
    IFamilyMembershipRepository,
)
from bounded_contexts.reward_points.domain.repositories.point_transaction_repository import (
    IPointTransactionRepository,
)
from bounded_contexts.reward_points.domain.services import family_access_policy
from bounded_contexts.reward_points.domain.services.ledger_statement import LedgerStatement


class ViewPointLedgerUseCase:
    def __init__(
        self,
        access: FamilyAccessResolver,
        transactions: IPointTransactionRepository,
        memberships: IFamilyMembershipRepository,
    ) -> None:
        self._access = access
        self._transactions = transactions
        self._memberships = memberships

    def execute(self, *, ledger_id: int, account_id: int) -> LedgerDTO:
        found = self._access.viewable_ledger(ledger_id=ledger_id, account_id=account_id)
        owner = self._memberships.find_by_id(found.ledger.membership_id)
        if owner is None:
            raise MembershipNotFoundError
        statement = LedgerStatement(self._transactions.list_by_ledger(ledger_id))
        return LedgerDTO(
            ledger_id=found.ledger.id,
            family_id=found.ledger.family_id,
            membership_id=owner.id,
            display_name=owner.display_name_value,
            balance=statement.balance.value,
            can_modify=family_access_policy.can_modify_ledger(found.membership, found.ledger),
            transactions=self._to_dtos(statement),
        )

    def _to_dtos(self, statement: LedgerStatement) -> tuple[TransactionDTO, ...]:
        reversed_ids = statement.reversed_transaction_ids
        actors = self._actor_names(statement.transactions)
        return tuple(
            TransactionDTO(
                id=transaction.id,
                amount=transaction.amount.value,
                reason=transaction.reason.value,
                occurred_at=transaction.occurred_at,
                created_at=transaction.created_at,
                reversal_of_id=transaction.reversal_of_id,
                is_reversed=transaction.id in reversed_ids,
                granted_by=actors.get(transaction.granted_by_membership_id or 0),
            )
            for transaction in statement.transactions
        )

    def _actor_names(self, transactions: tuple[PointTransaction, ...]) -> dict[int, str]:
        ids = {t.granted_by_membership_id for t in transactions if t.granted_by_membership_id is not None}
        return {m.id: m.display_name_value for m in self._memberships.list_by_ids(sorted(ids))}


__all__ = ["ViewPointLedgerUseCase"]
