"""Log lines buffered during a request (waiting to be written to the ``log`` table).

``DbLogHandler`` INSERTs each line over its own connection. Doing that mid-request
**collides with the write lock held by the request's session** (SQLite).
With the default ``sqlite:///app.db`` it fails after waiting the busy timeout (5 seconds) and the handler
swallows the exception, so "one log line takes 5 seconds and never reaches the DB".

So mid-request lines are buffered here and written together after the request finishes
(ADR-0012). Outside the middleware (startup code, scripts) nobody holds the lock,
so lines are written immediately.
"""

from __future__ import annotations

from contextvars import ContextVar

# One row to write (column name -> value). The handler builds it and the batch write INSERTs it as is.
LogRow = dict[str, object]


class PendingLogRecords:
    """Buffer for one request."""

    def __init__(self) -> None:
        self._rows: list[LogRow] = []

    def add(self, row: LogRow) -> None:
        self._rows.append(row)

    def drain(self) -> tuple[LogRow, ...]:
        """Take the buffered rows and empty the buffer (prevents double writes)."""
        rows = tuple(self._rows)
        self._rows.clear()
        return rows


_pending_records_var: ContextVar[PendingLogRecords | None] = ContextVar("pending_log_records", default=None)


def install_pending_log_records() -> PendingLogRecords:
    """Prepare and return this request's buffer (the middleware calls this first)."""
    pending = PendingLogRecords()
    _pending_records_var.set(pending)
    return pending


def current_pending_log_records() -> PendingLogRecords | None:
    """Buffer of the request in progress. ``None`` outside a request (write immediately)."""
    return _pending_records_var.get()


__all__ = [
    "LogRow",
    "PendingLogRecords",
    "current_pending_log_records",
    "install_pending_log_records",
]
