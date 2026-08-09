"""毎日のボーナスの決まり（ADR-0024）。

「どの日がまだ渡っていないか」と「1 日の区切り」の 2 つを見る。どちらも
時計にも DB にも触らないので、日付を直接渡して確かめる。
"""

from __future__ import annotations

from datetime import UTC, date, datetime
from zoneinfo import ZoneInfo

import pytest

from bounded_contexts.reward_points.domain.entities.daily_bonus import (
    DailyBonus,
    idempotency_key_for,
)
from bounded_contexts.reward_points.domain.services.day_boundary import DayBoundary
from bounded_contexts.reward_points.domain.value_objects.idempotency_key import is_derived
from bounded_contexts.reward_points.domain.value_objects.point_amount import PointAmount
from bounded_contexts.reward_points.domain.value_objects.transaction_reason import TransactionReason

_TOKYO = ZoneInfo("Asia/Tokyo")


def _bonus(*, starts_on: date, granted_through: date | None = None, amount: int = 10) -> DailyBonus:
    return DailyBonus(
        id=1,
        ledger_id=2,
        amount=PointAmount(amount),
        reason=TransactionReason("おこづかい"),
        starts_on=starts_on,
        granted_through=granted_through,
    )


# --- どの日を渡すか -----------------------------------------------------------


def test_the_first_day_is_the_day_it_was_decided() -> None:
    bonus = _bonus(starts_on=date(2026, 8, 9))

    due = bonus.due_days(today=date(2026, 8, 9), limit=31)

    assert due.days == (date(2026, 8, 9),)
    assert due.skipped == 0


def test_nothing_is_due_before_the_starting_day() -> None:
    """決めた日より前へは遡らない（設定した瞬間に身に覚えのない行が並ばない）。"""
    bonus = _bonus(starts_on=date(2026, 8, 9))

    assert bonus.due_days(today=date(2026, 8, 8), limit=31).days == ()


def test_a_day_already_granted_is_not_due_again() -> None:
    bonus = _bonus(starts_on=date(2026, 8, 1), granted_through=date(2026, 8, 9))

    assert bonus.due_days(today=date(2026, 8, 9), limit=31).days == ()


def test_days_missed_while_stopped_are_caught_up_in_order() -> None:
    bonus = _bonus(starts_on=date(2026, 8, 1), granted_through=date(2026, 8, 5))

    due = bonus.due_days(today=date(2026, 8, 8), limit=31)

    assert due.days == (date(2026, 8, 6), date(2026, 8, 7), date(2026, 8, 8))
    assert due.skipped == 0


def test_a_long_outage_keeps_the_most_recent_days_and_reports_the_rest() -> None:
    """上限を超えた分は **古い方** を捨てる。

    古い方から埋めると、上限に当たるたびに何日も前の行が増え続け、今日の分が
    着くまでに何周もかかる。捨てた日数は呼び出し側がログへ残せるよう返す。
    """
    bonus = _bonus(starts_on=date(2026, 1, 1))

    due = bonus.due_days(today=date(2026, 1, 10), limit=3)

    assert due.days == (date(2026, 1, 8), date(2026, 1, 9), date(2026, 1, 10))
    assert due.skipped == 7


def test_the_catch_up_limit_never_drops_today() -> None:
    """上限に 0 以下が設定されていても、今日の分だけは渡す。"""
    bonus = _bonus(starts_on=date(2026, 1, 1))

    due = bonus.due_days(today=date(2026, 1, 5), limit=0)

    assert due.days == (date(2026, 1, 5),)
    assert due.skipped == 4


def test_a_bonus_that_takes_points_away_is_rejected() -> None:
    with pytest.raises(ValueError, match="add points"):
        _bonus(starts_on=date(2026, 8, 9), amount=-10)


# --- 冪等キー ----------------------------------------------------------------


def test_the_same_day_always_produces_the_same_key() -> None:
    """二重付与を止めるのはこの性質（``UNIQUE (ledger_id, idempotency_key)``）。"""
    assert idempotency_key_for(date(2026, 8, 9)) == idempotency_key_for(date(2026, 8, 9))
    assert idempotency_key_for(date(2026, 8, 9)) != idempotency_key_for(date(2026, 8, 10))


def test_the_key_cannot_collide_with_one_sent_by_a_client() -> None:
    """段階付きの鍵（``#`` を含む）は API が受け取らない形。"""
    assert is_derived(idempotency_key_for(date(2026, 8, 9)))


# --- 1 日の区切り -------------------------------------------------------------


def test_the_day_is_decided_in_the_configured_time_zone() -> None:
    """UTC で 8/8 の 15:30 は、東京ではもう 8/9。"""
    moment = datetime(2026, 8, 8, 15, 30)

    assert DayBoundary(_TOKYO).day_of(moment) == date(2026, 8, 9)
    assert DayBoundary(UTC).day_of(moment) == date(2026, 8, 8)


def test_the_entry_lands_at_the_start_of_that_local_day() -> None:
    """東京の 8/9 0:00 は UTC の 8/8 15:00（保存は naive UTC）。"""
    assert DayBoundary(_TOKYO).starts_at(date(2026, 8, 9)) == datetime(2026, 8, 8, 15, 0)
    assert DayBoundary(UTC).starts_at(date(2026, 8, 9)) == datetime(2026, 8, 9, 0, 0)


def test_the_boundary_round_trips() -> None:
    """その日の始まりは、同じ区切りで見れば必ずその日。"""
    boundary = DayBoundary(_TOKYO)
    day = date(2026, 8, 9)

    assert boundary.day_of(boundary.starts_at(day)) == day
