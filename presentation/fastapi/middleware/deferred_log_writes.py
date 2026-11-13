"""Middleware that batch-writes app logs (the ``log`` table).

Log rows emitted during a request are written in one go **after the request has fully
finished**. Inserting from another connection mid-request collides with the write lock
held by the request's session, and on SQLite the rows are lost after the busy timeout
(5 seconds) (:mod:`shared.kernel.logging.pending_records`).

**Written as a plain ASGI middleware** (not ``BaseHTTPMiddleware``).
FastAPI closes ``yield`` dependencies (the ``get_db`` commit) **after** sending the
response, so the session is still open when ``call_next`` returns.
``await self.app(...)`` waits for the downstream to finish, so this reliably runs after commit / rollback.
"""

from __future__ import annotations

import logging

from starlette.types import ASGIApp, Receive, Scope, Send

from shared.kernel.logging.db_log_handler import write_log_rows
from shared.kernel.logging.pending_records import install_pending_log_records

# This logger is excluded by DbLogHandler (it lives under ``shared.kernel.logging``),
# so a log about a failed write does not trigger another write.
logger = logging.getLogger("shared.kernel.logging.deferred_writes")


class DeferredLogWriteMiddleware:
    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        pending = install_pending_log_records()
        try:
            await self.app(scope, receive, send)
        finally:
            try:
                write_log_rows(pending.drain())
            except Exception:
                # Even if the DB write fails, structured logs still went to stdout. Do not stop processing
                logger.exception("Failed to write logs to the DB")


__all__ = ["DeferredLogWriteMiddleware"]
