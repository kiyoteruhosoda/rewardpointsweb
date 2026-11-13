"""Mapping of domain exceptions -> HTTP responses.

Registered once as an application-wide exception handler so that routers do not
scatter ``try/except`` everywhere. The response body is just the error code; the
display text is decided by the frontend (CLAUDE.md "Internationalization").

Failures are recorded by the cross-cutting sink (:func:`~presentation.fastapi.error_handling.log_failed_request`).
Recording them separately here would mix in lines whose level and fields do not
match failures from ``HTTPException``, making the logs impossible to filter.
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
    # A configuration mistake cannot be fixed by the user. Return it as a server-side fault, not an input error (4xx).
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
            # Tell the client how long to wait (ADR-0055). The screen can show this as the wait time
            detail["retry_after_seconds"] = error.retry_after_seconds
            headers["Retry-After"] = str(error.retry_after_seconds)
        return JSONResponse(status_code=status_code, content={"detail": detail}, headers=headers)


__all__ = ["register_account_security_error_handler", "status_for"]
