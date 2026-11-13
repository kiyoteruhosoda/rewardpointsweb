"""Handling of times.

Times that are stored or compared are always UTC and written to the DB as naive datetime
(see CLAUDE.md "Logging"). Mixing values with and without tz info makes comparisons raise,
so creation is collected in this one place.

Converting times shown on screen to local time is the frontend's job; the server returns
UTC as is. However, **strings that leave the API always carry ``Z``** (``isoformat_utc``).
JavaScript's ``new Date()`` reads an ISO string without an offset as local time,
so forgetting it shifts the screen by 9 hours.
"""

from __future__ import annotations

from datetime import UTC, datetime


def utcnow() -> datetime:
    """Return the current time as a UTC naive datetime."""
    return datetime.now(UTC).replace(tzinfo=None)


def as_naive_utc(moment: datetime) -> datetime:
    """Normalize a time received from outside to a storable form (UTC naive datetime).

    API requests carry times with a time zone (``2026-07-30T09:00:00+09:00``).
    Storing them with tz makes comparisons with existing rows stored without tz raise.
    A time without tz is treated as already given in UTC.
    """
    if moment.tzinfo is None:
        return moment
    return moment.astimezone(UTC).replace(tzinfo=None)


def isoformat_utc(value: datetime) -> str:
    """ISO string for leaving the API. It always ends with ``Z``.

    Naive values are treated as UTC (stored values are UTC naive). Browsers read ISO strings
    without ``Z`` as local time, so every value crossing the boundary must
    go through here.
    """
    aware = value.replace(tzinfo=UTC) if value.tzinfo is None else value.astimezone(UTC)
    return aware.isoformat().replace("+00:00", "Z")


__all__ = ["as_naive_utc", "isoformat_utc", "utcnow"]
