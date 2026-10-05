"""ドメイン例外 -> HTTP 応答の対応付け（表示端末。ADR-0047）。"""

from __future__ import annotations

from fastapi import FastAPI, Request, status
from fastapi.responses import JSONResponse

from bounded_contexts.display_devices.domain.exceptions import (
    AuthorizationPendingError,
    DeviceCredentialExpiredError,
    DisplayDevicesError,
    ExpiredTokenError,
    InvalidDeviceCredentialError,
    PairingExpiredError,
    PairingNotFoundError,
)
from presentation.fastapi.error_handling import log_failed_request

_STATUS_BY_ERROR: dict[type[DisplayDevicesError], int] = {
    PairingNotFoundError: status.HTTP_404_NOT_FOUND,
    PairingExpiredError: status.HTTP_410_GONE,
    # 受け取りの口は RFC 8628 §3.5 に合わせて 400 で返す（まだ・期限切れの区別は ``error`` で）
    AuthorizationPendingError: status.HTTP_400_BAD_REQUEST,
    ExpiredTokenError: status.HTTP_400_BAD_REQUEST,
    # 端末はこれを受けたら資格情報を消し、ペアリングの画面へ戻る
    InvalidDeviceCredentialError: status.HTTP_401_UNAUTHORIZED,
    DeviceCredentialExpiredError: status.HTTP_401_UNAUTHORIZED,
}


def status_for(error: DisplayDevicesError) -> int:
    return _STATUS_BY_ERROR.get(type(error), status.HTTP_400_BAD_REQUEST)


def register_display_devices_error_handler(app: FastAPI) -> None:
    @app.exception_handler(DisplayDevicesError)
    async def _handle(request: Request, error: DisplayDevicesError) -> JSONResponse:
        status_code = status_for(error)
        # まだ承認されていない問い合わせは 5 秒ごとに来る。失敗として積まない
        if not isinstance(error, AuthorizationPendingError):
            log_failed_request(request, status_code, error.code)
        return JSONResponse(status_code=status_code, content={"detail": {"error": error.code}})


__all__ = ["register_display_devices_error_handler", "status_for"]
