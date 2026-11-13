"""What a ledger read returns (the history and the balance it implies).

The balance is not stored; it is derived with ``SUM(amount)``. With no expiry and
no periodic reset, the sum always covers every record in the ledger, so no
snapshots or expiry jobs are needed (ADR-0010).

Reversed IDs are enumerated once here so the screen can show "this was undone"
without looking each row up again.
"""

from __future__ import annotations

from collections.abc import Sequence

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

    @property
    def reversed_transaction_ids(self) -> frozenset[int]:
        """IDs of the reversed transactions. The UI uses these to show pairs."""
        return frozenset(
            transaction.reversal_of_id for transaction in self._transactions if transaction.reversal_of_id is not None
        )


__all__ = ["LedgerStatement"]
