"""リクエスト単位の構造化ログ（``requestId`` の採番と伝播）。

ログのレベルは応答のステータスコードで決める（:func:`~presentation.fastapi.error_handling.log_level_for_status`）。
成功だけを INFO で並べても異常は見つからないので、4xx は WARNING、5xx は ERROR
として、レベルで絞り込めば失敗だけが残るようにする。
"""

from __future__ import annotations

import logging
import time
import uuid

from starlette import status
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.requests import Request
from starlette.responses import Response

from presentation.fastapi.error_handling import log_level_for_status
from shared.kernel.logging.request_context import request_id_var, user_id_hash_var

access_logger = logging.getLogger("app.request")

# 死活監視・メトリクス収集の定期アクセス。Docker の healthcheck は数十秒おきに
# 叩くため、成功した分まで残すとアプリログがこれで埋まり、本当に見たい行が
# 押し流される（1 件ずつは「異常が無かった」以上の情報を持たない）。
# **失敗（4xx/5xx）は残す。** プローブが落ちていること自体が知りたい情報で、
# ここで捨てると監視の対象が監視できなくなる。
_PROBE_PATHS = frozenset({"/api/health", "/healthz", "/readyz", "/metrics"})


def _should_log(path: str, status_code: int) -> bool:
    return status_code >= status.HTTP_400_BAD_REQUEST or path not in _PROBE_PATHS


class RequestLoggingMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        request_id = str(uuid.uuid4())
        request_id_var.set(request_id)
        user_id_hash_var.set(None)
        start = time.perf_counter()

        response = await call_next(request)

        duration_ms = round((time.perf_counter() - start) * 1000, 2)
        if _should_log(request.url.path, response.status_code):
            access_logger.log(
                log_level_for_status(response.status_code),
                "http_request",
                extra={
                    "request_id": request_id,
                    "method": request.method,
                    "path": request.url.path,
                    "status_code": response.status_code,
                    "duration_ms": duration_ms,
                },
            )
        response.headers["X-Request-Id"] = request_id
        return response


__all__ = ["RequestLoggingMiddleware"]
