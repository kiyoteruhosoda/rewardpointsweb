"""What a ledger read returns (the history and the balance it implies).

The balance is not stored; it is derived with ``SUM(amount)``. With no expiry and
no periodic reset, the sum always covers every record in the ledger, so no
snapshots or expiry jobs are needed (ADR-0010).

Reversed IDs are enumerated once here so the screen can show "this was undone"
without looking each row up again.
"""

from __future__ import annotations

from collections.abc import Sequence
from datetime import datetime

from bounded_contexts.reward_points.domain.entities.point_transaction import PointTransaction
from bounded_contexts.reward_points.domain.value_objects.point_balance import PointBalance


class LedgerStatement:
    def __init__(self, transactions: Sequence[PointTransaction]) -> None:
        self._transactions = tuple(transactions)

    @property
    def transactions(self) -> tuple[PointTransaction, ...]:
        """Returned in the order given (ordering is the repository's job)."""
        return self._transactions

    @property
    def balance(self) -> PointBalance:
        return PointBalance(sum(transaction.signed_points for transaction in self._transactions))

    def earned_points_since(self, start: datetime) -> int:
        """Points added for things that happened at or after *start*, as the ledger stands now (ADR-0061).

        Spending never lowers it. Reversed records and the reversal rows themselves are left
        out as pairs, the same as the balance trend (ADR-0050): a reversed addition never
        happened, and a reversed spending gives nothing new. A correction's restated row is an
        ordinary row and counts if it adds; it keeps the original's occurrence time, so
        correcting a record from before *start* does not make it count.
        """
        reversed_ids = self.reversed_transaction_ids
        return sum(
            transaction.amount.value
            for transaction in self._transactions
            if transaction.amount.value > 0
            and transaction.reversal_of_id is None
            and transaction.id not in reversed_ids
            and transaction.occurred_at >= start
        )

    @property
    def reversed_transaction_ids(self) -> frozenset[int]:
        """IDs of the reversed transactions. The UI uses these to show pairs."""
        return frozenset(
            transaction.reversal_of_id for transaction in self._transactions if transaction.reversal_of_id is not None
        )


__all__ = ["LedgerStatement"]
