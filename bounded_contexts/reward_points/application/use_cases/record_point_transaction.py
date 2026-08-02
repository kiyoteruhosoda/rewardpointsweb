"""台帳へ 1 行追記する（加算・消費）。

符号で加算と消費を表すため、2 つのユースケースに分けない。残高検証は行わない
（マイナス残高を許容する。ADR-0010）。

``idempotency_key`` はクライアントが生成する。同じ台帳へ同じキーで届いた
2 度目以降は、エラーにせず 1 度目のレコードを返す（送信ボタンの二重タップで
二重登録しないための約束）。
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from bounded_contexts.reward_points.application.dto.ledger_dto import TransactionDTO, just_written
from bounded_contexts.reward_points.application.family_access_resolver import FamilyAccessResolver
from bounded_contexts.reward_points.domain.repositories.point_transaction_repository import (
    IPointTransactionRepository,
    NewTransaction,
)
from shared.kernel.timestamps import as_naive_utc, utcnow


@dataclass(frozen=True, kw_only=True)
class RecordTransactionCommand:
    ledger_id: int
    account_id: int
    amount: int
    reason: str
    idempotency_key: str
    occurred_at: datetime | None


class RecordPointTransactionUseCase:
    def __init__(self, access: FamilyAccessResolver, transactions: IPointTransactionRepository) -> None:
        self._access = access
        self._transactions = transactions

    def execute(self, command: RecordTransactionCommand) -> TransactionDTO:
        found = self._access.modifiable_ledger(ledger_id=command.ledger_id, account_id=command.account_id)
        transaction = self._transactions.append(
            NewTransaction(
                ledger_id=found.ledger.id,
                amount=command.amount,
                reason=command.reason,
                granted_by_membership_id=found.membership.id,
                occurred_at=as_naive_utc(command.occurred_at) if command.occurred_at else utcnow(),
                idempotency_key=command.idempotency_key,
            )
        )
        return just_written(transaction, granted_by=found.membership.display_name_value)


__all__ = ["RecordPointTransactionUseCase", "RecordTransactionCommand"]
