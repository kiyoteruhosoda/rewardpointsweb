"""Handler that writes to the ``log`` table.

- ``requestId`` is taken from the record (attached by ``RequestContextFilter``).
- No DB connection, before migration, or a write failure never breaks the main work (but
  is not silent either: ``handleError`` reports it to stderr).
- SQLAlchemy's own logs are excluded because writing them would recurse.
- **During a request, rows are only buffered**; the actual INSERT is done in one go by
  :class:`~presentation.fastapi.middleware.deferred_log_writes.DeferredLogWriteMiddleware`
  after the request finishes. Writing over another connection mid-request collides with
  the write lock held by the request's session (:mod:`shared.kernel.logging.pending_records`).
"""

from __future__ import annotations

import logging
import traceback as tb_module
from collections.abc import Sequence

import sqlalchemy as sa

from shared.kernel.logging.pending_records import (
    LogRow,
    current_pending_log_records,
)

_EXCLUDED_LOGGER_PREFIXES = ("sqlalchemy", "alembic", "shared.kernel.logging")


def write_log_rows(rows: Sequence[LogRow]) -> None:
    """Write the buffered rows in one transaction.

    Called after the request finishes (by the middleware). Exceptions are raised
    as is (whether to swallow them is up to the caller).
    """
    if not rows:
        return
    from shared.infrastructure.models.log import Log
    from shared.kernel.database.db import get_engine

    with get_engine().begin() as connection:
        connection.execute(sa.insert(Log), list(rows))


class DbLogHandler(logging.Handler):
    def emit(self, record: logging.LogRecord) -> None:
        if record.name.startswith(_EXCLUDED_LOGGER_PREFIXES):
            return
        try:
            from shared.kernel.settings.settings import settings

            if not settings.log_to_database:
                return

            row = _to_row(record)
            pending = current_pending_log_records()
            if pending is None:
                # Outside a request (startup code, scripts). Nothing to contend with
                write_log_rows([row])
            else:
                pending.add(row)
        except Exception:
            # Logging must not break the main work. But it must **not be silent**: making this
            # ``pass`` leaves "logs do not appear in the admin screen" as the only symptom,
            # and nobody sees the cause (no DB connection, before migration, column mismatch).
            # ``handleError`` only prints the traceback to stderr and does not re-enter
            # logging (no path that tries to write to the DB and fails again).
            self.handleError(record)


def _to_row(record: logging.LogRecord) -> LogRow:
    from shared.infrastructure.models.base import utcnow

    trace = None
    if record.exc_info and record.exc_info[0] is not None:
        trace = "".join(tb_module.format_exception(*record.exc_info))

    # The duration_ms column is Integer. SQLite's type affinity keeps a float as is,
    # so round before writing to make both backends behave the same.
    duration_ms = getattr(record, "duration_ms", None)
    if duration_ms is not None:
        duration_ms = round(float(duration_ms))

    return {
        "created_at": utcnow(),
        "level": record.levelname,
        "logger": record.name[:120],
        "message": record.getMessage(),
        "request_id": getattr(record, "request_id", None),
        "user_id_hash": getattr(record, "user_id_hash", None),
        "path": getattr(record, "path", None),
        "method": getattr(record, "method", None),
        "status_code": getattr(record, "status_code", None),
        "duration_ms": duration_ms,
        "trace": trace,
    }


__all__ = ["DbLogHandler", "write_log_rows"]
