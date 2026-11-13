"""Counting failures per identifier (ADR-0055).

Holds "refuse for *L* after *N* failures within the window" as **decisions and state transitions only**.
What "now" is is passed in from outside. It knows neither the DB nor the request.

The unit counted is **the identifier that was sent**, not an existing account.
Counting only existing ones would reveal existence by whether the request is refused.
"""

from __future__ import annotations

from dataclasses import dataclass, replace
from datetime import datetime, timedelta

# Purposes. Since DB-native ENUMs are not used, allowed values are managed on the Python side.
PURPOSE_LOGIN = "login"
PURPOSE_PASSWORD_RESET = "password_reset"
ATTEMPT_PURPOSES: tuple[str, ...] = (PURPOSE_LOGIN, PURPOSE_PASSWORD_RESET)


@dataclass(frozen=True)
class ThrottlePolicy:
    """How many failures to allow within the window, and how long to refuse once exceeded.

    If ``max_failures`` is 0, **nothing is counted** (a development convenience; never 0 in production).
    """

    max_failures: int
    window: timedelta
    lock_duration: timedelta

    @property
    def enabled(self) -> bool:
        return self.max_failures > 0


@dataclass(frozen=True)
class LoginAttempts:
    """Failure record for one identifier.

    *window_started_at* is when counting started. Failures past the window restart the count.
    While *locked_until* is set, requests are refused.
    """

    purpose: str
    identifier: str
    failures: int = 0
    window_started_at: datetime | None = None
    locked_until: datetime | None = None

    def retry_after(self, now: datetime) -> timedelta | None:
        """If refusing, how much longer to wait. ``None`` if not refusing."""
        if self.locked_until is None or now >= self.locked_until:
            return None
        return self.locked_until - now

    def after_failure(self, now: datetime, policy: ThrottlePolicy) -> LoginAttempts:
        """One failure. Outside the window, restart the count; at the limit, start refusing."""
        if self.window_started_at is None or now - self.window_started_at >= policy.window:
            failures, started = 1, now
        else:
            failures, started = self.failures + 1, self.window_started_at
        locked_until = now + policy.lock_duration if failures >= policy.max_failures else None
        return replace(self, failures=failures, window_started_at=started, locked_until=locked_until)

    def after_success(self) -> LoginAttempts:
        """Entered correctly. Earlier failures were typos, so forget them."""
        return replace(self, failures=0, window_started_at=None, locked_until=None)

    def is_stale(self, now: datetime, policy: ThrottlePolicy) -> bool:
        """No longer worth remembering (both the window and the refusal have passed). Subject to cleanup."""
        if self.locked_until is not None and now < self.locked_until:
            return False
        return self.window_started_at is None or now - self.window_started_at >= policy.window


__all__ = [
    "ATTEMPT_PURPOSES",
    "PURPOSE_LOGIN",
    "PURPOSE_PASSWORD_RESET",
    "LoginAttempts",
    "ThrottlePolicy",
]
