"""Deriving the balance, and how reversals appear (ADR-0010)."""

from __future__ import annotations

from dataclasses import replace
from datetime import datetime, timedelta

from bounded_contexts.reward_points.domain.entities.point_transaction import PointTransaction
from bounded_contexts.reward_points.domain.services.ledger_statement import LedgerStatement
from bounded_contexts.reward_points.domain.value_objects.point_amount import PointAmount
from bounded_contexts.reward_points.domain.value_objects.transaction_reason import TransactionReason

_MOMENT = datetime(2026, 8, 1, 0, 0, 0)


def _transaction(
    *, id: int, amount: int, reversal_of_id: int | None = None, corrects_id: int | None = None
) -> PointTransaction:
    return PointTransaction(
        id=id,
        ledger_id=1,
        amount=PointAmount(amount),
        reason=TransactionReason("おてつだい"),
        granted_by_membership_id=1,
        occurred_at=_MOMENT,
        created_at=_MOMENT,
        reversal_of_id=reversal_of_id,
        corrects_id=corrects_id,
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


# --- Points earned since the egg was handed over (the pet; ADR-0061) -----------------

_EGG_DAY = datetime(2026, 11, 16, 0, 0, 0)


def _at(transaction: PointTransaction, moment: datetime) -> PointTransaction:
    return replace(transaction, occurred_at=moment)


def test_spending_never_lowers_what_was_earned() -> None:
    statement = LedgerStatement([_transaction(id=1, amount=100), _transaction(id=2, amount=-80)])

    assert statement.earned_points_since(_MOMENT) == 100


def test_points_from_before_the_egg_was_handed_over_do_not_count() -> None:
    statement = LedgerStatement(
        [
            _at(_transaction(id=1, amount=10_000), _EGG_DAY - timedelta(days=1)),
            _at(_transaction(id=2, amount=40), _EGG_DAY),
            _at(_transaction(id=3, amount=60), _EGG_DAY + timedelta(hours=3)),
        ]
    )

    assert statement.earned_points_since(_EGG_DAY) == 100


def test_a_reversed_addition_was_never_earned() -> None:
    statement = LedgerStatement(
        [
            _transaction(id=1, amount=100),
            _transaction(id=2, amount=50),
            _transaction(id=3, amount=-50, reversal_of_id=2),
        ]
    )

    assert statement.earned_points_since(_MOMENT) == 100


def test_reversing_a_spending_earns_nothing_new() -> None:
    statement = LedgerStatement(
        [
            _transaction(id=1, amount=100),
            _transaction(id=2, amount=-30),
            _transaction(id=3, amount=30, reversal_of_id=2),
        ]
    )

    assert statement.earned_points_since(_MOMENT) == 100


def test_a_corrected_addition_counts_at_its_corrected_amount() -> None:
    statement = LedgerStatement(
        [
            _transaction(id=1, amount=100),
            _transaction(id=2, amount=-100, reversal_of_id=1),
            _transaction(id=3, amount=10, corrects_id=1),
        ]
    )

    assert statement.earned_points_since(_MOMENT) == 10


def test_correcting_a_record_from_before_the_egg_does_not_make_it_count() -> None:
    before = _EGG_DAY - timedelta(days=3)
    statement = LedgerStatement(
        [
            _at(_transaction(id=1, amount=100), before),
            _at(_transaction(id=2, amount=-100, reversal_of_id=1), _EGG_DAY + timedelta(hours=1)),
            # The restated row keeps the original's occurrence time (ADR-0022)
            _at(_transaction(id=3, amount=10, corrects_id=1), before),
        ]
    )

    assert statement.earned_points_since(_EGG_DAY) == 0
