"""Mapping of domain exceptions -> HTTP responses (display devices, ADR-0047)."""

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
    # The token endpoint returns 400 per RFC 8628 §3.5 (pending vs. expired is told apart by ``error``)
    AuthorizationPendingError: status.HTTP_400_BAD_REQUEST,
    ExpiredTokenError: status.HTTP_400_BAD_REQUEST,
    # On this, the device deletes its credential and returns to the pairing screen
    InvalidDeviceCredentialError: status.HTTP_401_UNAUTHORIZED,
    DeviceCredentialExpiredError: status.HTTP_401_UNAUTHORIZED,
}


def status_for(error: DisplayDevicesError) -> int:
    return _STATUS_BY_ERROR.get(type(error), status.HTTP_400_BAD_REQUEST)


def register_display_devices_error_handler(app: FastAPI) -> None:
    @app.exception_handler(DisplayDevicesError)
    async def _handle(request: Request, error: DisplayDevicesError) -> JSONResponse:
        status_code = status_for(error)
        # Polls for a not-yet-approved pairing arrive every 5 seconds; do not record them as failures
        if not isinstance(error, AuthorizationPendingError):
            log_failed_request(request, status_code, error.code)
        return JSONResponse(status_code=status_code, content={"detail": {"error": error.code}})


__all__ = ["register_display_devices_error_handler", "status_for"]
