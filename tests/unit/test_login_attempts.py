"""Counting failures and how to refuse (ADR-0055).

What we most want to check: **failures outside the window are counted afresh**, **refusal lifts
with time**, and **a successful sign-in forgets them**.
"""

from __future__ import annotations

from datetime import datetime, timedelta

from bounded_contexts.account_security.domain.entities.login_attempts import (
    PURPOSE_LOGIN,
    LoginAttempts,
    ThrottlePolicy,
)

NOW = datetime(2026, 10, 21, 12, 0, 0)
POLICY = ThrottlePolicy(max_failures=3, window=timedelta(minutes=15), lock_duration=timedelta(minutes=10))


def _fresh() -> LoginAttempts:
    return LoginAttempts(purpose=PURPOSE_LOGIN, identifier="someone@example.com")


def _fail(times: int, start: datetime = NOW, step: timedelta = timedelta(seconds=10)) -> LoginAttempts:
    attempts = _fresh()
    for index in range(times):
        attempts = attempts.after_failure(start + step * index, POLICY)
    return attempts


def test_nothing_is_refused_before_the_limit() -> None:
    assert _fail(2).retry_after(NOW + timedelta(seconds=30)) is None


def test_reaching_the_limit_refuses_for_the_lock_duration() -> None:
    locked = _fail(3)
    locked_at = NOW + timedelta(seconds=20)

    assert locked.retry_after(locked_at) == timedelta(minutes=10)
    assert locked.retry_after(locked_at + timedelta(minutes=9)) == timedelta(minutes=1)
    # Lifts with time. No admin action needed
    assert locked.retry_after(locked_at + timedelta(minutes=10)) is None


def test_failures_outside_the_window_are_counted_afresh() -> None:
    # 2 failures, then 1 more 20 minutes later. Past the window (15 min), so it counts as the first
    attempts = _fail(2).after_failure(NOW + timedelta(minutes=20), POLICY)

    assert attempts.failures == 1
    assert attempts.window_started_at == NOW + timedelta(minutes=20)
    assert attempts.locked_until is None


def test_success_forgets_everything() -> None:
    cleared = _fail(3).after_success()

    assert cleared.failures == 0
    assert cleared.locked_until is None
    assert cleared.retry_after(NOW) is None


def test_a_disabled_policy_never_counts() -> None:
    assert ThrottlePolicy(max_failures=0, window=POLICY.window, lock_duration=POLICY.lock_duration).enabled is False
    assert POLICY.enabled is True


def test_stale_rows_are_those_past_both_the_window_and_the_lock() -> None:
    locked = _fail(3)
    # Not deleted while refusing
    assert locked.is_stale(NOW + timedelta(minutes=5), POLICY) is False
    # Can be deleted once both the refusal and the window have passed
    assert locked.is_stale(NOW + timedelta(minutes=30), POLICY) is True
    # Failures inside the window are kept
    assert _fail(1).is_stale(NOW + timedelta(minutes=5), POLICY) is False
    assert _fresh().is_stale(NOW, POLICY) is True
