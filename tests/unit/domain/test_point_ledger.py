"""残高は履歴の合計として導出される。"""

from __future__ import annotations

from datetime import datetime

import pytest

from bounded_contexts.reward_points.domain.entities.point_entry import (
    PointAddition,
    PointConsumption,
    PointEntry,
)
from bounded_contexts.reward_points.domain.services.point_ledger import PointLedger
from bounded_contexts.reward_points.domain.value_objects.entry_description import EntryDescription
from bounded_contexts.reward_points.domain.value_objects.point_amount import PointAmount
from bounded_contexts.reward_points.domain.value_objects.point_entry_type import PointEntryType

_MOMENT = datetime(2026, 7, 30, 9, 0, 0)


def _addition(points: int, *, entry_id: int = 1) -> PointAddition:
    return PointAddition(
        id=entry_id,
        member_id=1,
        occurred_at=_MOMENT,
        amount=PointAmount(points),
        recorded_by_user_id=10,
        reason=EntryDescription("お手伝い"),
    )


def _consumption(points: int, *, entry_id: int = 2) -> PointConsumption:
    return PointConsumption(
        id=entry_id,
        member_id=1,
        occurred_at=_MOMENT,
        amount=PointAmount(points),
        recorded_by_user_id=10,
        application=EntryDescription("おかし"),
    )


def test_empty_ledger_has_zero_balance() -> None:
    assert PointLedger([]).balance.value == 0


def test_addition_increases_and_consumption_decreases() -> None:
    ledger = PointLedger([_addition(100), _consumption(30)])

    assert ledger.balance.value == 70


def test_balance_can_go_negative() -> None:
    """記録の順序を運用に合わせられるよう、消費が残高を超えても記録は拒まない。"""
    assert PointLedger([_addition(10), _consumption(50)]).balance.value == -40


def test_balance_is_independent_of_order() -> None:
    entries: list[PointEntry] = [_addition(100), _consumption(30)]

    assert PointLedger(entries).balance == PointLedger(list(reversed(entries))).balance


def test_entries_keep_the_given_order() -> None:
    entries: list[PointEntry] = [_consumption(30), _addition(100)]

    assert PointLedger(entries).entries == tuple(entries)


@pytest.mark.parametrize(
    ("entry", "expected_type", "expected_signed", "expected_description"),
    [
        (_addition(100), PointEntryType.ADDITION, 100, "お手伝い"),
        (_consumption(100), PointEntryType.CONSUMPTION, -100, "おかし"),
    ],
)
def test_each_entry_type_knows_its_own_sign_and_description(
    entry: PointEntry, expected_type: PointEntryType, expected_signed: int, expected_description: str
) -> None:
    assert entry.entry_type is expected_type
    assert entry.signed_points == expected_signed
    assert entry.description.value == expected_description
