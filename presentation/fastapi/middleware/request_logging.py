"""Per-request structured logging (assigning and propagating ``requestId``).

The log level is chosen from the response status code (:func:`~presentation.fastapi.error_handling.log_level_for_status`).
Listing successes at INFO alone does not surface problems, so 4xx is WARNING and 5xx is ERROR;
filtering by level then leaves only the failures.

**Written as a plain ASGI middleware** (not ``BaseHTTPMiddleware``).
``BaseHTTPMiddleware`` runs the downstream in **a separate task**, so the ``user_id_hash``
set by the auth dependency never comes back to the logging side, and only the ``http_request``
lines lose "whose request it was" (same reason as :mod:`presentation.fastapi.middleware.internal_error`).

The line is emitted **when the start of the response is sent**, without waiting for the downstream
to finish. For large streamed files ``duration_ms`` stays the time to the first byte, and the line
survives even if the connection drops midway.
"""

from __future__ import annotations

import logging
import time
import uuid

from starlette import status
from starlette.datastructures import MutableHeaders
from starlette.requests import Request
from starlette.types import ASGIApp, Message, Receive, Scope, Send

from presentation.fastapi.error_handling import log_level_for_status
from shared.kernel.logging.request_context import request_id_var, user_id_hash_var

access_logger = logging.getLogger("app.request")

# Periodic hits from liveness checks and metrics collection. The Docker healthcheck
# fires every few tens of seconds, so keeping the successful ones floods the app log
# and pushes out the lines that matter (each one says nothing beyond "nothing was wrong").
# **Failures (4xx/5xx) are kept.** A failing probe is exactly what we want to know,
# and dropping it here would leave the monitored thing unmonitored.
_PROBE_PATHS = frozenset({"/api/health", "/healthz", "/readyz", "/metrics"})


def _should_log(path: str, status_code: int) -> bool:
    return status_code >= status.HTTP_400_BAD_REQUEST or path not in _PROBE_PATHS


class RequestLoggingMiddleware:
    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        request = Request(scope)
        request_id = str(uuid.uuid4())
        request_id_var.set(request_id)
        user_id_hash_var.set(None)
        start = time.perf_counter()

        async def _send(message: Message) -> None:
            if message["type"] == "http.response.start":
                status_code = message["status"]
                duration_ms = round((time.perf_counter() - start) * 1000, 2)
                if _should_log(request.url.path, status_code):
                    access_logger.log(
                        log_level_for_status(status_code),
                        "http_request",
                        extra={
                            "request_id": request_id,
                            "method": request.method,
                            "path": request.url.path,
                            "status_code": status_code,
                            "duration_ms": duration_ms,
                        },
                    )
                MutableHeaders(scope=message)["X-Request-Id"] = request_id
            await send(message)

        await self.app(scope, receive, _send)


__all__ = ["RequestLoggingMiddleware"]
