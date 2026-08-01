"""残高の導出と、打ち消しの見え方（ADR-0010）。"""

from __future__ import annotations

from datetime import datetime

from bounded_contexts.reward_points.domain.entities.point_transaction import PointTransaction
from bounded_contexts.reward_points.domain.services.ledger_statement import LedgerStatement
from bounded_contexts.reward_points.domain.value_objects.point_amount import PointAmount
from bounded_contexts.reward_points.domain.value_objects.transaction_reason import TransactionReason

_MOMENT = datetime(2026, 8, 1, 0, 0, 0)


def _transaction(*, id: int, amount: int, reversal_of_id: int | None = None) -> PointTransaction:
    return PointTransaction(
        id=id,
        ledger_id=1,
        amount=PointAmount(amount),
        reason=TransactionReason("おてつだい"),
        granted_by_membership_id=1,
        occurred_at=_MOMENT,
        created_at=_MOMENT,
        reversal_of_id=reversal_of_id,
    )


def test_empty_ledger_has_zero_balance() -> None:
    assert LedgerStatement([]).balance.value == 0


def test_balance_is_the_signed_sum() -> None:
    statement = LedgerStatement([_transaction(id=1, amount=100), _transaction(id=2, amount=-30)])

    assert statement.balance.value == 70
    assert not statement.balance.is_negative


def test_balance_may_go_negative() -> None:
    statement = LedgerStatement([_transaction(id=1, amount=-50)])

    assert statement.balance.value == -50
    assert statement.balance.is_negative


def test_reversal_cancels_the_original_without_removing_it() -> None:
    statement = LedgerStatement([_transaction(id=1, amount=100), _transaction(id=2, amount=-100, reversal_of_id=1)])

    assert statement.balance.value == 0
    assert len(statement.transactions) == 2
    assert statement.reversed_transaction_ids == frozenset({1})


def test_order_is_left_to_the_repository() -> None:
    rows = [_transaction(id=2, amount=10), _transaction(id=1, amount=20)]

    assert [t.id for t in LedgerStatement(rows).transactions] == [2, 1]
