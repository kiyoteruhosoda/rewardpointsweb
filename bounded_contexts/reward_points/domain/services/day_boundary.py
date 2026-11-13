"""Day boundary.

Stored and compared times are always UTC (``shared.kernel.timestamps``), but
cutting "every day" at 00:00 UTC would make 9 a.m. the date change for a family
in Japan. To align the day in daily life with the day on the ledger, this holds
the one time zone used for the boundary.

Times passed in and out are **naive UTC datetimes**; awareness of the time zone
stays inside this class. If callers mixed tz-aware and naive values, every
comparison would raise (ADR-0024).
"""

from __future__ import annotations

from datetime import UTC, date, datetime, time, tzinfo


class DayBoundary:
    def __init__(self, time_zone: tzinfo) -> None:
        self._time_zone = time_zone

    def day_of(self, moment: datetime) -> date:
        """Which day *moment* (a naive UTC datetime) falls on under this boundary."""
        return moment.replace(tzinfo=UTC).astimezone(self._time_zone).date()

    def starts_at(self, day: date) -> datetime:
        """Start of *day* (a naive UTC datetime).

        Used as a grant's ``occurred_at`` so it lines up in the ledger as that day's
        event. It differs from the actual write time (``created_at``), so even when
        days missed during downtime are caught up at once, the history lands on
        each respective date.
        """
        return datetime.combine(day, time.min, tzinfo=self._time_zone).astimezone(UTC).replace(tzinfo=None)


__all__ = ["DayBoundary"]
