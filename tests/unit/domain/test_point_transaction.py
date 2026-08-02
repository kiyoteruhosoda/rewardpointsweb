"""打ち消し（ADR-0010）と訂正（ADR-0022）の組み立て。"""

from __future__ import annotations

from datetime import datetime

import pytest

from bounded_contexts.reward_points.domain.entities.point_transaction import PointTransaction
from bounded_contexts.reward_points.domain.exceptions import (
    CorrectionOfReversalError,
    ReversalOfReversalError,
)
from bounded_contexts.reward_points.domain.value_objects.point_amount import PointAmount
from bounded_contexts.reward_points.domain.value_objects.transaction_reason import TransactionReason

_MOMENT = datetime(2026, 8, 1, 0, 0, 0)


def _transaction(*, amount: int, reversal_of_id: int | None = None, corrects_id: int | None = None) -> PointTransaction:
    return PointTransaction(
        id=7,
        ledger_id=1,
        amount=PointAmount(amount),
        reason=TransactionReason("まちがい"),
        granted_by_membership_id=1,
        occurred_at=_MOMENT,
        created_at=_MOMENT,
        reversal_of_id=reversal_of_id,
        corrects_id=corrects_id,
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


def test_correction_carries_the_new_content_and_points_at_the_original() -> None:
    draft = _transaction(amount=100).plan_correction(amount=50, reason="おてつだい")

    assert draft.amount.value == 50
    assert draft.reason.value == "おてつだい"
    assert draft.corrects_id == 7
    assert draft.ledger_id == 1


def test_correction_keeps_the_original_moment_unless_asked_otherwise() -> None:
    """量や理由を直しただけで、出来事の日時が今日へ動かないこと。"""
    draft = _transaction(amount=100).plan_correction(amount=50, reason="おてつだい")

    assert draft.occurred_at == _MOMENT


def test_correction_can_move_the_moment() -> None:
    moved = datetime(2026, 7, 20, 9, 0, 0)

    draft = _transaction(amount=100).plan_correction(amount=50, reason="おてつだい", occurred_at=moved)

    assert draft.occurred_at == moved


def test_correction_may_flip_addition_into_consumption() -> None:
    """符号の付け間違い（加算のつもりが消費）も訂正で直せる。"""
    assert _transaction(amount=-100).plan_correction(amount=100, reason="おてつだい").amount.value == 100


def test_a_reversal_cannot_be_corrected() -> None:
    reversal = _transaction(amount=-100, reversal_of_id=3)

    with pytest.raises(CorrectionOfReversalError):
        reversal.plan_correction(amount=50, reason="おてつだい")


def test_a_correction_can_be_corrected_again() -> None:
    """訂正の内容を打ち間違えても、もう一度直せる。"""
    correction = _transaction(amount=50, corrects_id=3)

    assert correction.is_correction
    assert correction.plan_correction(amount=60, reason="おてつだい").corrects_id == 7


def test_zero_is_not_a_correction() -> None:
    with pytest.raises(ValueError, match="zero"):
        _transaction(amount=100).plan_correction(amount=0, reason="おてつだい")
