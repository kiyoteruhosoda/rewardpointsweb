"""Rules of the daily bonus (ADR-0024).

Looks at two things: "which days have not been granted yet" and "where a day ends". Neither
touches the clock or the DB, so dates are passed in directly.
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


# --- Which days to grant -----------------------------------------------------


def test_the_starting_day_is_the_first_one_due() -> None:
    bonus = _bonus(starts_on=date(2026, 8, 9))

    due = bonus.due_days(today=date(2026, 8, 9), limit=31)

    assert due.days == (date(2026, 8, 9),)
    assert due.skipped == 0


def test_nothing_is_due_before_the_starting_day() -> None:
    """Do not go back before the start date (no unfamiliar rows appear the moment it is set up)."""
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
    """What exceeds the limit drops the **oldest** days.

    Filling from the oldest would keep adding rows from days ago each time the limit is hit,
    taking many rounds before today's arrives. Returns the dropped day count so the caller can log it.
    """
    bonus = _bonus(starts_on=date(2026, 1, 1))

    due = bonus.due_days(today=date(2026, 1, 10), limit=3)

    assert due.days == (date(2026, 1, 8), date(2026, 1, 9), date(2026, 1, 10))
    assert due.skipped == 7


def test_the_catch_up_limit_never_drops_today() -> None:
    """Even if the limit is set to 0 or less, today's is still granted."""
    bonus = _bonus(starts_on=date(2026, 1, 1))

    due = bonus.due_days(today=date(2026, 1, 5), limit=0)

    assert due.days == (date(2026, 1, 5),)
    assert due.skipped == 4


def test_a_bonus_that_takes_points_away_is_rejected() -> None:
    with pytest.raises(ValueError, match="add points"):
        _bonus(starts_on=date(2026, 8, 9), amount=-10)


# --- Idempotency key -----------------------------------------------------------


def test_the_same_day_always_produces_the_same_key() -> None:
    """This property (``UNIQUE (ledger_id, idempotency_key)``) is what stops double grants."""
    assert idempotency_key_for(date(2026, 8, 9)) == idempotency_key_for(date(2026, 8, 9))
    assert idempotency_key_for(date(2026, 8, 9)) != idempotency_key_for(date(2026, 8, 10))


def test_the_key_cannot_collide_with_one_sent_by_a_client() -> None:
    """A staged key (containing ``#``) is a form the API does not accept."""
    assert is_derived(idempotency_key_for(date(2026, 8, 9)))


# --- Where a day ends ----------------------------------------------------------


def test_the_day_is_decided_in_the_configured_time_zone() -> None:
    """15:30 on 8/8 in UTC is already 8/9 in Tokyo."""
    moment = datetime(2026, 8, 8, 15, 30)

    assert DayBoundary(_TOKYO).day_of(moment) == date(2026, 8, 9)
    assert DayBoundary(UTC).day_of(moment) == date(2026, 8, 8)


def test_the_entry_lands_at_the_start_of_that_local_day() -> None:
    """0:00 on 8/9 in Tokyo is 15:00 on 8/8 UTC (stored as naive UTC)."""
    assert DayBoundary(_TOKYO).starts_at(date(2026, 8, 9)) == datetime(2026, 8, 8, 15, 0)
    assert DayBoundary(UTC).starts_at(date(2026, 8, 9)) == datetime(2026, 8, 9, 0, 0)


def test_the_boundary_round_trips() -> None:
    """The start of a day, viewed with the same boundary, is always that day."""
    boundary = DayBoundary(_TOKYO)
    day = date(2026, 8, 9)

    assert boundary.day_of(boundary.starts_at(day)) == day
