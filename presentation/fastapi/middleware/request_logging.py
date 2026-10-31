"""リクエスト単位の構造化ログ（``requestId`` の採番と伝播）。

ログのレベルは応答のステータスコードで決める（:func:`~presentation.fastapi.error_handling.log_level_for_status`）。
成功だけを INFO で並べても異常は見つからないので、4xx は WARNING、5xx は ERROR
として、レベルで絞り込めば失敗だけが残るようにする。

**素の ASGI ミドルウェアとして書いている**（``BaseHTTPMiddleware`` を使わない）。
``BaseHTTPMiddleware`` は下流を**別のタスク**で走らせるため、認証依存関数が設定した
``user_id_hash`` がログを出す側へ戻らず、``http_request`` の行だけ「誰のリクエストか」
が空になる（:mod:`presentation.fastapi.middleware.internal_error` と同じ事情）。

行を出すのは**応答の先頭を送るとき**で、下流が終わるのを待たない。大きなファイルの
流し読みでも ``duration_ms`` は先頭までの時間のままで、途中で接続が切れても行は残る。
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

# 死活監視・メトリクス収集の定期アクセス。Docker の healthcheck は数十秒おきに
# 叩くため、成功した分まで残すとアプリログがこれで埋まり、本当に見たい行が
# 押し流される（1 件ずつは「異常が無かった」以上の情報を持たない）。
# **失敗（4xx/5xx）は残す。** プローブが落ちていること自体が知りたい情報で、
# ここで捨てると監視の対象が監視できなくなる。
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
