"""ドメイン例外 → HTTP 応答の対応付け。

ルーターごとに ``try/except`` を書き散らさないよう、アプリケーション全体の
例外ハンドラとして一度だけ登録する。応答本文はエラーコードのみで、表示文言は
フロントエンドが決める（CLAUDE.md「国際化」）。

失敗の記録は横断的な受け皿（:func:`~presentation.fastapi.error_handling.log_failed_request`）
へ委ねる。ここで独自に記録すると、``HTTPException`` 由来の失敗とレベルや
フィールドの揃わない行が混ざり、ログを絞り込めなくなる。
"""

from __future__ import annotations

from fastapi import FastAPI, Request, status
from fastapi.responses import JSONResponse

from bounded_contexts.account_security.domain.exceptions import (
    AccountSecurityError,
    ChallengeNotFoundError,
    InvalidTotpCodeError,
    InvalidWebAuthnOriginError,
    InvalidWebAuthnRelyingPartyIdError,
    PasskeyAlreadyRegisteredError,
    PasskeyConfigurationError,
    PasskeyNotFoundError,
    PasskeyVerificationError,
    TooManyAttemptsError,
    TotpAlreadyEnabledError,
    TotpNotEnrolledError,
    TotpRequiredError,
)
from presentation.fastapi.error_handling import log_failed_request

_STATUS_BY_ERROR: dict[type[AccountSecurityError], int] = {
    ChallengeNotFoundError: status.HTTP_400_BAD_REQUEST,
    InvalidTotpCodeError: status.HTTP_400_BAD_REQUEST,
    # 設定の誤りは利用者に直せない。入力の誤り（4xx）ではなくサーバー側の不備として返す。
    InvalidWebAuthnOriginError: status.HTTP_500_INTERNAL_SERVER_ERROR,
    InvalidWebAuthnRelyingPartyIdError: status.HTTP_500_INTERNAL_SERVER_ERROR,
    PasskeyAlreadyRegisteredError: status.HTTP_409_CONFLICT,
    PasskeyConfigurationError: status.HTTP_500_INTERNAL_SERVER_ERROR,
    PasskeyNotFoundError: status.HTTP_404_NOT_FOUND,
    PasskeyVerificationError: status.HTTP_401_UNAUTHORIZED,
    TotpAlreadyEnabledError: status.HTTP_409_CONFLICT,
    TotpNotEnrolledError: status.HTTP_409_CONFLICT,
    TotpRequiredError: status.HTTP_401_UNAUTHORIZED,
    TooManyAttemptsError: status.HTTP_429_TOO_MANY_REQUESTS,
}


def status_for(error: AccountSecurityError) -> int:
    return _STATUS_BY_ERROR.get(type(error), status.HTTP_400_BAD_REQUEST)


def register_account_security_error_handler(app: FastAPI) -> None:
    @app.exception_handler(AccountSecurityError)
    async def _handle(request: Request, error: AccountSecurityError) -> JSONResponse:
        status_code = status_for(error)
        log_failed_request(request, status_code, error.code)
        detail: dict[str, str | int] = {"error": error.code}
        headers: dict[str, str] = {}
        if isinstance(error, TooManyAttemptsError):
            # いつまで待てばよいかを返す（ADR-0055）。画面はこれを待ち時間として出せる
            detail["retry_after_seconds"] = error.retry_after_seconds
            headers["Retry-After"] = str(error.retry_after_seconds)
        return JSONResponse(status_code=status_code, content={"detail": detail}, headers=headers)


__all__ = ["register_account_security_error_handler", "status_for"]
