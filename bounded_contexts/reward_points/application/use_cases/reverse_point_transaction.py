"""Reverse a record (correction).

The original record is never rewritten. A row with the opposite sign is added, linked
via ``reversal_of_id``. Double reversal is also blocked by a UNIQUE constraint in the DB,
but it is turned into a clear error code here first. A reversal record itself cannot be
reversed (ADR-0010).
"""

from __future__ import annotations

from dataclasses import dataclass

from bounded_contexts.reward_points.application.dto.ledger_dto import TransactionDTO, just_written
from bounded_contexts.reward_points.application.family_access_resolver import FamilyAccessResolver
from bounded_contexts.reward_points.domain.exceptions import (
    TransactionAlreadyReversedError,
    TransactionNotFoundError,
)
from bounded_contexts.reward_points.domain.repositories.point_transaction_repository import (
    IPointTransactionRepository,
    NewTransaction,
)
from shared.kernel.timestamps import utcnow


@dataclass(frozen=True, kw_only=True)
class ReverseTransactionCommand:
    ledger_id: int
    transaction_id: int
    account_id: int
    idempotency_key: str


class ReversePointTransactionUseCase:
    def __init__(self, access: FamilyAccessResolver, transactions: IPointTransactionRepository) -> None:
        self._access = access
        self._transactions = transactions

    def execute(self, command: ReverseTransactionCommand) -> TransactionDTO:
        found = self._access.modifiable_ledger(ledger_id=command.ledger_id, account_id=command.account_id)
        original = self._transactions.find_in_ledger(ledger_id=command.ledger_id, transaction_id=command.transaction_id)
        if original is None:
            raise TransactionNotFoundError
        if self._transactions.find_reversal_of(original.id) is not None:
            raise TransactionAlreadyReversedError
        draft = original.plan_reversal()
        reversal = self._transactions.append(
            NewTransaction(
                ledger_id=draft.ledger_id,
                amount=draft.amount.value,
                reason=draft.reason.value,
                granted_by_membership_id=found.membership.id,
                occurred_at=utcnow(),
                idempotency_key=command.idempotency_key,
                reversal_of_id=draft.reversal_of_id,
            )
        )
        return just_written(reversal, granted_by=found.membership.display_name_value)


__all__ = ["ReversePointTransactionUseCase", "ReverseTransactionCommand"]
