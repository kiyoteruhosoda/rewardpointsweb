"""FastAPI JWT authentication dependencies.

Verifies JWTs via ``Depends()`` and passes the verified ``AuthenticatedPrincipal`` to
routers. Authorization is declared with :func:`require_permission` (scope based).
"""

from __future__ import annotations

import logging
from collections.abc import Awaitable, Callable

from fastapi import Cookie, Depends, HTTPException, Response, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from shared.application.authenticated_principal import AuthenticatedPrincipal
from shared.kernel.database.session import get_db
from shared.kernel.logging.request_context import user_id_hash_var
from shared.kernel.settings.settings import settings

logger = logging.getLogger(__name__)

# Name of the cookie holding the access token (set by the auth router at login)
ACCESS_TOKEN_COOKIE = "access_token"


def set_access_token_cookie(response: Response, token: str) -> None:
    """Put the access token into the cookie.

    There are several paths that issue tokens (password, refresh, passkey), so the cookie
    attributes are set in this one place.
    """
    response.set_cookie(
        ACCESS_TOKEN_COOKIE,
        token,
        max_age=settings.access_token_expires_seconds,
        httponly=True,
        secure=settings.session_cookie_secure,
        samesite="lax",
    )


def clear_access_token_cookie(response: Response) -> None:
    response.delete_cookie(ACCESS_TOKEN_COOKIE)


# Prefer the Authorization header; fall back to the cookie
_bearer_scheme = HTTPBearer(auto_error=False)


def _extract_token(
    credentials: HTTPAuthorizationCredentials | None,
    access_token_cookie: str | None,
) -> str | None:
    if credentials and credentials.scheme.lower() == "bearer":
        return credentials.credentials
    return access_token_cookie or None


async def get_current_principal(
    credentials: HTTPAuthorizationCredentials | None = Depends(_bearer_scheme),
    access_token_cookie: str | None = Cookie(default=None, alias=ACCESS_TOKEN_COOKIE),
) -> AuthenticatedPrincipal:
    """Verify the JWT and return ``AuthenticatedPrincipal``. 401 on failure."""
    from presentation.fastapi.services.token_service import TokenService

    token = _extract_token(credentials, access_token_cookie)
    if not token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={"error": "authentication_required"},
            headers={"WWW-Authenticate": "Bearer"},
        )

    principal, reason = TokenService.verify_access_token_with_reason(token)
    if not principal:
        logger.debug("JWT authentication failed: %s", reason)
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={"error": "invalid_token", "reason": reason},
            headers={"WWW-Authenticate": "Bearer"},
        )

    # Propagate user.id_hash to subsequent logs (no PII)
    user_id_hash_var.set(principal.id_hash)
    return principal


async def get_active_principal(
    principal: AuthenticatedPrincipal = Depends(get_current_principal),
) -> AuthenticatedPrincipal:
    """Refuse while logged in with a temporary password (ADR-0011).

    **Paths that need authentication go through here as a rule.** Only three may use
    :func:`get_current_principal` directly: the password change path
    (``POST /api/auth/change-password``) and the who-am-I paths
    (``GET /api/auth/me`` / ``POST /api/auth/logout``). If 2FA / passkey registration and removal
    were open too, whoever holds the temporary password could swap the second factor before the owner.
    """
    if principal.must_change_password:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={"error": "password_change_required"},
        )
    return principal


async def get_current_principal_or_none(
    access_token_cookie: str | None = Cookie(default=None, alias=ACCESS_TOKEN_COOKIE),
) -> AuthenticatedPrincipal | None:
    """Return the principal if signed in, ``None`` otherwise (no 401).

    ⚠ **Do not use this for authorization.** It is only for paths reached by a **browser
    navigation** (the return from linking in ADR-0036). Returning 401 there would show the user
    nothing but raw JSON, with no way to retry. Endpoints that need authorization use
    :func:`get_active_principal`.
    """
    from presentation.fastapi.services.token_service import TokenService

    if not access_token_cookie:
        return None
    principal, _ = TokenService.verify_access_token_with_reason(access_token_cookie)
    return principal


async def get_person_principal(
    principal: AuthenticatedPrincipal = Depends(get_active_principal),
) -> AuthenticatedPrincipal:
    """Allow **person sessions** only. Display devices (ADR-0047) are refused.

    Display devices have neither credentials (2FA, passkeys, SSO links) nor a profile.
    ⚠ If they did, someone standing at the device could create **a way in that survives being
    removed** (e.g. add an email address and grow a password via reset). Credential- and
    profile-changing paths go through here.
    """
    if principal.via_display_device:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={"error": "display_device_not_allowed"},
        )
    return principal


def get_settled_principal(
    principal: AuthenticatedPrincipal = Depends(get_person_principal),
    db: Session = Depends(get_db),
) -> AuthenticatedPrincipal:
    """Gate for **credential-changing paths** (ADR-0037).

    ⚠ **Only here is the row re-read.** Access token verification no longer hits the DB
    (ADR-0037), so the temporary-password flag is the value baked into the token. If, right after
    a parent sets a temporary password, a child could **swap 2FA or passkeys with the token they
    hold, setting it would be pointless** (ADR-0011).

    ⚠ **Disabled users are also rejected here**, so they cannot create new credentials.
    Display devices are rejected too (via :func:`get_person_principal`).
    """
    from presentation.fastapi.services.token_service import TokenService

    user = TokenService.load_active_user(principal.user_id, session=db)
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={"error": "invalid_token"},
        )
    if user.must_change_password:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={"error": "password_change_required"},
        )
    return principal


def require_permission(*codes: str) -> Callable[..., Awaitable[AuthenticatedPrincipal]]:
    """Dependency factory that allows access only when all the given permissions are held.

    Example::

        @router.get("/api/admin/users")
        def list_users(
            principal: AuthenticatedPrincipal = Depends(require_permission("user:manage")),
        ):
            ...
    """

    async def _check(
        principal: AuthenticatedPrincipal = Depends(get_active_principal),
    ) -> AuthenticatedPrincipal:
        if not principal.can(*codes):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail={
                    "error": "forbidden",
                    "message": f"Required permissions: {', '.join(codes)}",
                },
            )
        return principal

    return _check


__all__ = [
    "ACCESS_TOKEN_COOKIE",
    "clear_access_token_cookie",
    "get_active_principal",
    "get_current_principal",
    "get_person_principal",
    "get_settled_principal",
    "require_permission",
    "set_access_token_cookie",
]
