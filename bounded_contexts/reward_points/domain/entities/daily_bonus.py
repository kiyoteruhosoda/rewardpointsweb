"""Daily bonus (ADR-0024).

One per child ledger. It holds "how many points to add each day", and when the
date changes one row is appended to the ledger. The append itself follows the
ledger's rules, so this only handles **which days have not been granted yet**.

``granted_through`` remembers how far it has granted. The next run grants
everything from the following day through today, so days when the app was down
are not skipped. But recovering an unlimited backlog after a long outage would
fill a long-unopened ledger with hundreds of bonus rows. So the number of days
to go back is capped, and the excess is returned as a count so the caller can
say it was dropped.

Double grants are stopped by an idempotency key (``UNIQUE (ledger_id,
idempotency_key)``; ADR-0010). The key is derived from the date itself, so even
granting the same day twice puts only one row in the ledger, whether several
workers run at once or a catch-up dies midway and restarts. It is a stepped key
(``daily-bonus#2026-08-09``) because keys sent by users never contain ``#``
(:func:`~...idempotency_key.is_derived`). A bonus row and a hand-written row
never collide on the same key.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, timedelta

from bounded_contexts.reward_points.domain.value_objects.idempotency_key import IdempotencyKey
from bounded_contexts.reward_points.domain.value_objects.point_amount import PointAmount
from bounded_contexts.reward_points.domain.value_objects.transaction_reason import TransactionReason

#: Base of the idempotency key. Used with the date added as a step (``daily-bonus#2026-08-09``)
IDEMPOTENCY_BASE = "daily-bonus"


def idempotency_key_for(day: date) -> str:
    """Idempotency key for the grant of *day*. The same day always yields the same value."""
    return IdempotencyKey(IDEMPOTENCY_BASE).for_step(day.isoformat()).value


@dataclass(frozen=True, kw_only=True)
class DueDays:
    """Days not yet granted, and the number of days dropped by the cap."""

    days: tuple[date, ...]
    #: Number of days not granted because they exceed the look-back cap. 0 means nothing was missed
    skipped: int


@dataclass(frozen=True, kw_only=True)
class DailyBonus:
    id: int
    ledger_id: int
    amount: PointAmount
    reason: TransactionReason
    #: First day to grant. Never goes back before it (the Application layer decides it)
    starts_on: date
    #: Last day already granted. ``None`` if no day has been granted yet
    granted_through: date | None

    def __post_init__(self) -> None:
        # A setting that subtracts every day is not a "bonus". Spending is recorded by hand
        if self.amount.value <= 0:
            raise ValueError("Daily bonus must add points")

    def due_days(self, *, today: date, limit: int) -> DueDays:
        """Return the days due up to *today*, oldest first.

        If there are more than ``limit``, grant only the **newest** ``limit`` days.
        Filling from the oldest after a long pause would keep adding rows from days
        ago each time the cap is hit, taking many rounds before today's bonus lands.
        """
        first = self.granted_through + timedelta(days=1) if self.granted_through else self.starts_on
        if today < first:
            return DueDays(days=(), skipped=0)
        total = (today - first).days + 1
        skipped = max(0, total - max(1, limit))
        start = first + timedelta(days=skipped)
        return DueDays(
            days=tuple(start + timedelta(days=offset) for offset in range(total - skipped)),
            skipped=skipped,
        )


__all__ = ["IDEMPOTENCY_BASE", "DailyBonus", "DueDays", "idempotency_key_for"]
