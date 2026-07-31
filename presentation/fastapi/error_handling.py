"""想定外の例外 → HTTP 応答の対応付け（最後の受け皿）。

受け皿が無いと、Starlette は本文 ``Internal Server Error`` の **text/plain** を
返す。API クライアント（SPA）は本文を JSON として読むため、これを受け取ると
「エラーコードが読めない応答」に落ち、画面には一律 ``unknown_error`` の文言しか
出せない。原因の切り分けもできない。

そこで、どのルーターでも拾えなかった例外は

- ``{"detail": {"error": "internal_error"}}`` の JSON へ揃え（表示文言は
  フロントエンドが決める。CLAUDE.md「国際化」）
- traceback つきでログへ残す（``log`` テーブルの ``trace`` 列へ入る）

を行う。ドメイン例外の対応付けは各コンテキストの ``error_handling`` が担うので、
ここへ個別の例外を足さない。

受け皿は**二重**に置く。

1. :class:`~presentation.fastapi.middleware.internal_error.InternalErrorMiddleware`
   （通常の経路）。CORS・リクエストログの**内側**に置くため、応答に CORS
   ヘッダーと ``X-Request-Id`` が付き、アクセスログにも 500 として残る。
2. ``Exception`` ハンドラ（保険）。1 より外側のミドルウェア自身が落ちた場合に
   だけ働く。Starlette はこのハンドラを ``ServerErrorMiddleware``（全ミドル
   ウェアの外側）へ載せるため、ここから返す応答には CORS ヘッダーが付かない。
   通常の経路を 1 に任せているのはこのため。
"""

from __future__ import annotations

import logging

from fastapi import FastAPI, Request, status
from fastapi.responses import JSONResponse

from shared.kernel.logging.request_context import current_request_id

logger = logging.getLogger(__name__)

INTERNAL_ERROR_CODE = "internal_error"


def internal_error_response(request: Request, error: Exception) -> JSONResponse:
    """例外を記録し、エラーコードだけを返す 500 応答を組み立てる。

    例外の中身は応答に出さない（内部構造の露出を避ける）。追跡は ``requestId``
    で行う。
    """
    logger.exception(
        "unhandled_exception",
        extra={"method": request.method, "path": request.url.path},
        exc_info=error,
    )
    request_id = current_request_id()
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={"detail": {"error": INTERNAL_ERROR_CODE}},
        headers={"X-Request-Id": request_id} if request_id else None,
    )


def register_internal_error_handler(app: FastAPI) -> None:
    """ミドルウェアより外側で起きた例外のための保険を登録する。"""

    @app.exception_handler(Exception)
    async def _handle(request: Request, error: Exception) -> JSONResponse:
        return internal_error_response(request, error)


__all__ = [
    "INTERNAL_ERROR_CODE",
    "internal_error_response",
    "register_internal_error_handler",
]
