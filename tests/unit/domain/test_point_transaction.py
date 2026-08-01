"""打ち消しの組み立て（ADR-0010）。"""

from __future__ import annotations

from datetime import datetime

import pytest

from bounded_contexts.reward_points.domain.entities.point_transaction import PointTransaction
from bounded_contexts.reward_points.domain.exceptions import ReversalOfReversalError
from bounded_contexts.reward_points.domain.value_objects.point_amount import PointAmount
from bounded_contexts.reward_points.domain.value_objects.transaction_reason import TransactionReason

_MOMENT = datetime(2026, 8, 1, 0, 0, 0)


def _transaction(*, amount: int, reversal_of_id: int | None = None) -> PointTransaction:
    return PointTransaction(
        id=7,
        ledger_id=1,
        amount=PointAmount(amount),
        reason=TransactionReason("まちがい"),
        granted_by_membership_id=1,
        occurred_at=_MOMENT,
        created_at=_MOMENT,
        reversal_of_id=reversal_of_id,
    )


def test_reversal_flips_the_sign_and_keeps_the_reason() -> None:
    draft = _transaction(amount=100).plan_reversal()

    assert draft.amount.value == -100
    assert draft.reason.value == "まちがい"
    assert draft.reversal_of_id == 7
    assert draft.ledger_id == 1


def test_consumption_is_reversed_into_an_addition() -> None:
    assert _transaction(amount=-40).plan_reversal().amount.value == 40


def test_a_reversal_cannot_be_reversed() -> None:
    reversal = _transaction(amount=-100, reversal_of_id=3)

    assert reversal.is_reversal
    with pytest.raises(ReversalOfReversalError):
        reversal.plan_reversal()
