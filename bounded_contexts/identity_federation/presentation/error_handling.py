"""Mapping of domain exceptions -> HTTP responses.

This handles only the **routes that return JSON** (``POST /api/auth/sso/token`` and
``/api/auth/sso/link``).
``/login`` and ``/callback``, used for browser navigation, catch exceptions in the router itself
and turn them into a redirect to the login screen (the SPA cannot read a JSON response there).
"""

from __future__ import annotations

from fastapi import FastAPI, Request, status
from fastapi.responses import JSONResponse

from bounded_contexts.identity_federation.domain.exceptions import (
    IdentityFederationError,
    IdentityProviderUnavailableError,
    InvalidLogoutTokenError,
    SsoAlreadyLinkedError,
    SsoIdentityNotLinkedError,
    SsoIdentityTakenError,
    SsoLastEntranceError,
    SsoNotConfiguredError,
    SsoTicketNotFoundError,
)
from presentation.fastapi.error_handling import log_failed_request

_STATUS_BY_ERROR: dict[type[IdentityFederationError], int] = {
    IdentityProviderUnavailableError: status.HTTP_502_BAD_GATEWAY,
    SsoNotConfiguredError: status.HTTP_404_NOT_FOUND,
    SsoTicketNotFoundError: status.HTTP_401_UNAUTHORIZED,
    # The logout notice is sent by the IdP, not by a user. Returning 401 would read as
    # "re-authenticate", so return "invalid request" as the spec says (Back-Channel Logout 1.0 §2.8).
    InvalidLogoutTokenError: status.HTTP_400_BAD_REQUEST,
    # Unlinking / linking (ADR-0036). ⚠ **Do not return 401** -- the caller has already
    # authenticated; if it reads as "re-authenticate", the user repeats a pointless action.
    SsoIdentityNotLinkedError: status.HTTP_404_NOT_FOUND,
    SsoIdentityTakenError: status.HTTP_409_CONFLICT,
    SsoAlreadyLinkedError: status.HTTP_409_CONFLICT,
    SsoLastEntranceError: status.HTTP_409_CONFLICT,
}


def status_for(error: IdentityFederationError) -> int:
    """Default is 401: every SSO failure means the login did not go through."""
    return _STATUS_BY_ERROR.get(type(error), status.HTTP_401_UNAUTHORIZED)


def register_identity_federation_error_handler(app: FastAPI) -> None:
    @app.exception_handler(IdentityFederationError)
    async def _handle(request: Request, error: IdentityFederationError) -> JSONResponse:
        status_code = status_for(error)
        log_failed_request(request, status_code, error.code)
        return JSONResponse(status_code=status_code, content={"detail": {"error": error.code}})


__all__ = ["register_identity_federation_error_handler", "status_for"]
