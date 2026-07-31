"""想定外の例外 → HTTP 応答の対応付け（最後の受け皿）。

ハンドラを登録しないと、Starlette は本文 ``Internal Server Error`` の
**text/plain** を返す。API クライアント（SPA）は本文を JSON として読むため、
これを受け取ると「エラーコードが読めない応答」に落ち、画面には一律
``unknown_error`` の文言しか出せない。原因の切り分けもできない。

そこで、どのルーターでも拾えなかった例外はここで

- ``{"detail": {"error": "internal_error"}}`` の JSON へ揃え（表示文言は
  フロントエンドが決める。CLAUDE.md「国際化」）
- ``requestId`` を応答ヘッダーへ載せ（ログの該当行を引ける）
- traceback 付きでログへ残す（``log`` テーブルの ``trace`` 列へ入る）

を行う。ドメイン例外の対応付けは各コンテキストの ``error_handling`` が担うので、
ここへ個別の例外を足さない。
"""

from __future__ import annotations

import logging

from fastapi import FastAPI, Request, status
from fastapi.responses import JSONResponse

from shared.kernel.logging.request_context import current_request_id

logger = logging.getLogger(__name__)

INTERNAL_ERROR_CODE = "internal_error"


def register_internal_error_handler(app: FastAPI) -> None:
    @app.exception_handler(Exception)
    async def _handle(request: Request, error: Exception) -> JSONResponse:
        # 例外の中身は応答に出さない（内部構造の露出を避ける）。追跡は requestId で行う。
        logger.exception(
            "unhandled_exception",
            extra={"method": request.method, "path": request.url.path},
            exc_info=error,
        )
        request_id = current_request_id()
        headers = {"X-Request-Id": request_id} if request_id else None
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content={"detail": {"error": INTERNAL_ERROR_CODE}},
            headers=headers,
        )


__all__ = ["INTERNAL_ERROR_CODE", "register_internal_error_handler"]
