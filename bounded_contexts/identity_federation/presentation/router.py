"""SSO (OpenID Connect) login API.

Main routes.

- ``GET /provider`` — asks whether the login screen should show the "sign in with SSO" button
- ``GET /login`` — sends the browser to the IdP's authorization endpoint
- ``GET /renew`` — starts a round trip that continues an expired login without a screen
  (inside a hidden frame; ADR-0058)
- ``GET /callback`` — return from the IdP. Goes back to the SPA with an exchange ticket
  (to the result page for a continuing round trip)
- ``GET /renewed`` — result page of a continuing round trip (the screen reads where the frame ended up)
- ``POST /token`` — exchanges the ticket for tokens (cookies are set here too)
- ``POST /backchannel-logout`` — receives revocation notices from the IdP (ADR-0032)

``/login`` sends the browser out **after giving it a passphrase cookie**. The record table is
shared by everyone, so anyone who merely knows ``state`` could complete the return
(if an attacker makes a victim open an authorization request the attacker started, the victim ends up
signed in as the attacker: login CSRF). ``/callback`` also checks that this cookie matches.

``/login`` and ``/callback`` are **browser navigations**, and the SPA cannot read the response body.
So failures are returned not as JSON but as a redirect to the login screen (``?sso_error=<code>``).
The display text is decided by the frontend (CLAUDE.md "Internationalization").

The exchange ticket that keeps tokens out of URLs is ADR-0029.
"""

from __future__ import annotations

import logging
import re
from typing import Annotated
from urllib.parse import parse_qsl, quote, urlencode

from fastapi import APIRouter, Cookie, Depends, HTTPException, Query, Request, Response, status
from fastapi.responses import RedirectResponse
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session
from starlette.concurrency import run_in_threadpool

from bounded_contexts.account_security.application.use_cases.count_local_factors import (
    CountLocalFactors,
)
from bounded_contexts.account_security.infrastructure.sql_local_factor_directory import (
    SqlLocalFactorDirectory,
)
from bounded_contexts.identity_federation.application.dto.sso_dto import ResolvedAccountDto
from bounded_contexts.identity_federation.application.use_cases.complete_sso_link import (
    CompleteSsoLink,
)
from bounded_contexts.identity_federation.application.use_cases.complete_sso_login import (
    CompleteSsoLogin,
)
from bounded_contexts.identity_federation.application.use_cases.describe_federated_link import (
    DescribeFederatedLink,
)
from bounded_contexts.identity_federation.application.use_cases.describe_round_trip import (
    DescribeRoundTrip,
)
from bounded_contexts.identity_federation.application.use_cases.describe_sso_provider import (
    DescribeSsoProvider,
)
from bounded_contexts.identity_federation.application.use_cases.exchange_sso_ticket import (
    ExchangeSsoTicket,
)
from bounded_contexts.identity_federation.application.use_cases.receive_backchannel_logout import (
    ReceiveBackchannelLogout,
)
from bounded_contexts.identity_federation.application.use_cases.start_sso_link import (
    StartSsoLink,
)
from bounded_contexts.identity_federation.application.use_cases.start_sso_login import (
    StartSsoLogin,
)
from bounded_contexts.identity_federation.application.use_cases.unlink_federated_identity import (
    UnlinkFederatedIdentity,
)
from bounded_contexts.identity_federation.domain.exceptions import (
    IdentityFederationError,
    InvalidLogoutTokenError,
    SsoLinkSessionMismatchError,
    SsoNotConfiguredError,
)
from bounded_contexts.identity_federation.domain.value_objects.sso_callback import (
    SsoCallback,
)
from bounded_contexts.identity_federation.presentation import dependencies, renewal
from bounded_contexts.identity_federation.presentation.schemas import (
    FederatedLinkResponse,
    SsoLinkStartResponse,
    SsoProviderResponse,
    SsoSessionResponse,
    SsoTicketRequest,
)
from presentation.fastapi.dependencies.auth import (
    get_active_principal,
    get_current_principal_or_none,
    get_person_principal,
    set_access_token_cookie,
)
from presentation.fastapi.schemas.auth import StatusResponse
from presentation.fastapi.services.token_service import TokenService, continued_user_of
from shared.application.authenticated_principal import AuthenticatedPrincipal
from shared.infrastructure.models import User
from shared.kernel.database.session import get_db
from shared.kernel.settings.settings import settings

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/auth/sso", tags=["auth"])

DbDep = Annotated[Session, Depends(get_db)]

# SPA routes to return to (keep in sync with the frontend routing)
LOGIN_SCREEN = "/login"
HANDOFF_SCREEN = "/login/sso"
#: Landing point of a linking return (the security settings screen; ADR-0036)
SECURITY_SCREEN = "/security"

# Passphrase given to the browser that issued the authorization request. It is ``SameSite=Lax`` because
# the return from the IdP is **a GET navigation from another site** (with ``Strict`` it would not be
# sent on return, and legitimate logins would always fail).
SSO_BINDING_COOKIE = "sso_binding"

# Error codes returned by the IdP go straight into the screen URL, so only well-formed ones pass
# (so links cannot be built from reflected strings). Matching uses ``fullmatch`` --
# ``$`` also matches just before a trailing newline, so ``match`` would let a newline through.
_ERROR_CODE = re.compile(r"[a-z_]{1,64}")
_GENERIC_ERROR = "sso_error"

#: Codes the IdP returns for "a screen is needed" on a round trip tried without a screen (``prompt=none``)
#: (OIDC Core §3.1.2.6). **Not a failure**, so go back to the login screen without an error (ADR-0052).
#: ``access_denied`` is when signed in to Assay but not permitted to use this app (task #648).
_SILENT_DECLINES = frozenset(
    {
        "login_required",
        "consent_required",
        "interaction_required",
        "account_selection_required",
        "access_denied",
    }
)
#: Marker that a try came back. The login screen does not retry when it is present (loop stopper).
SILENT_DECLINED_PARAM = "sso_silent"


class SsoCallbackQuery:
    """Query on the return from the IdP (``code`` and ``state`` on success)."""

    def __init__(
        self,
        code: Annotated[str | None, Query(max_length=2048)] = None,
        state: Annotated[str | None, Query(max_length=255)] = None,
        error: Annotated[str | None, Query(max_length=255)] = None,
    ) -> None:
        self.code = code
        self.state = state
        self.error = error


@router.get("/provider", response_model=SsoProviderResponse)
async def describe_provider(
    use_case: Annotated[DescribeSsoProvider, Depends(dependencies.describe_sso_provider)],
) -> SsoProviderResponse:
    """Answer whether SSO is available (callable unauthenticated; does not return endpoint details)."""
    provider = use_case.execute()
    return SsoProviderResponse(enabled=provider.enabled, display_name=provider.display_name)


# ``/login`` and ``/callback`` make synchronous HTTP calls to the IdP (discovery, token exchange).
# With ``async def`` the event loop would block for that round trip, making every request in the
# same worker wait. Defining them with ``def`` offloads them to the thread pool.
@router.get("/login", include_in_schema=False)
def start_login(
    use_case: Annotated[StartSsoLogin, Depends(dependencies.start_sso_login)],
    redirect_to: Annotated[str | None, Query(max_length=255)] = None,
    # Unknown values are ignored (it is a navigation, so do not show a 422 JSON)
    prompt: Annotated[str | None, Query(max_length=16)] = None,
) -> RedirectResponse:
    """Send out to the IdP. If not configured or the IdP is unreachable, go back to the login screen.

    The login screen adds ``?prompt=none`` itself when it opens (ADR-0052). If signed in at the IdP,
    the user gets in without pressing the button; if not, it comes back without showing a screen.
    """
    try:
        authorization = use_case.execute(redirect_to=redirect_to, silent=prompt == "none")
    except IdentityFederationError as error:
        logger.warning("sso_start_failed: %s", error.code)
        return _to_login_screen(error.code)
    response = RedirectResponse(url=authorization.authorization_url, status_code=status.HTTP_303_SEE_OTHER)
    _set_binding_cookie(response, authorization.browser_binding)
    return response


@router.get("/renew", include_in_schema=False)
def start_renewal(
    use_case: Annotated[StartSsoLogin, Depends(dependencies.start_sso_login)],
) -> RedirectResponse:
    """Start a round trip continuing an expired login without a screen (ADR-0058).
    **The screen opens it in a hidden frame.**

    Always ``prompt=none``. If the IdP is unreachable, go to the result page (``failed``).
    """
    try:
        authorization = use_case.renew()
    except IdentityFederationError as error:
        logger.warning("sso_renewal_start_failed: %s", error.code)
        return _renewal_result(renewal.RenewalResult.FAILED)
    response = RedirectResponse(url=authorization.authorization_url, status_code=status.HTTP_303_SEE_OTHER)
    _set_binding_cookie(response, authorization.browser_binding)
    renewal.allow_same_origin_framing(response)
    return response


@router.get("/renewed", include_in_schema=False)
def renewal_result() -> Response:
    """Result page of a continuing round trip (the screen reads ``result`` and ``ticket`` from the frame URL)."""
    return renewal.result_page()


def _set_binding_cookie(response: Response, binding: str) -> None:
    """Give the outgoing browser a passphrase (stops login CSRF)."""
    response.set_cookie(
        SSO_BINDING_COOKIE,
        binding,
        max_age=settings.oidc_login_session_ttl_seconds,
        httponly=True,
        secure=settings.session_cookie_secure,
        samesite="lax",
        path=router.prefix,
    )


class _CallbackTools:
    """Tools needed to wrap up the return (ADR-0036).

    The login return and the linking return are received on one route, so both sets of tools are gathered here
    (to keep handler arguments from growing; written the same way as ``SsoCallbackQuery``).
    """

    def __init__(
        self,
        *,
        login: Annotated[CompleteSsoLogin, Depends(dependencies.complete_sso_login)],
        link: Annotated[CompleteSsoLink, Depends(dependencies.complete_sso_link)],
        purpose: Annotated[DescribeRoundTrip, Depends(dependencies.describe_round_trip)],
        viewer: Annotated[AuthenticatedPrincipal | None, Depends(get_current_principal_or_none)] = None,
    ) -> None:
        self.login = login
        self.link = link
        self.purpose = purpose
        self.viewer = viewer


@router.get("/callback", include_in_schema=False)
def complete_callback(
    *,
    query: Annotated[SsoCallbackQuery, Depends()],
    tools: Annotated[_CallbackTools, Depends()],
    binding: Annotated[str | None, Cookie(alias=SSO_BINDING_COOKIE)] = None,
) -> RedirectResponse:
    """Receive the return from the IdP. Serves both login returns and linking returns (ADR-0036).

    The passphrase cookie is dropped on success and failure alike (used up in one round trip).

    ⚠ **The record knows which round trip it is.** It is not passed in the query -- otherwise
    rewriting the return URL alone could disguise it.
    """
    if query.state and tools.purpose.is_renewal(state=query.state, browser_binding=binding):
        return _complete_renewal(query, tools, binding)
    if query.error in _SILENT_DECLINES and query.state:
        declined_to = tools.purpose.silently_declined(state=query.state, browser_binding=binding)
        if declined_to is not None:
            return _silently_declined(declined_to)
    if query.error is not None or not query.code or not query.state:
        return _failed(query.error or "sso_callback_invalid")
    callback = SsoCallback(code=query.code, state=query.state, browser_binding=binding)
    if tools.purpose.execute(state=query.state) is not None:
        return _complete_link(callback, tools)
    return _complete_login(callback, tools)


def _complete_login(callback: SsoCallback, tools: _CallbackTools) -> RedirectResponse:
    """Go back to the SPA with an exchange ticket."""
    try:
        handoff = tools.login.execute(
            code=callback.code, state=callback.state, browser_binding=callback.browser_binding
        )
    except IdentityFederationError as error:
        return _failed(error.code)
    _log_account_changes(handoff.account)
    return _redirect(f"{HANDOFF_SCREEN}?ticket={quote(handoff.ticket)}")


def _log_account_changes(account: ResolvedAccountDto) -> None:
    if account.provisioned:
        # A round trip that created an account is logged under a different name (ADR-0041). It records a new user.
        logger.info("sso_account_provisioned")
    elif account.linked:
        # Log one line only for a round trip that linked for the first time (who it was is traced from requestId;
        # CLAUDE.md "Logging").
        logger.info("sso_identity_linked")


def _complete_renewal(query: SsoCallbackQuery, tools: _CallbackTools, binding: str | None) -> RedirectResponse:
    """Return of a continuing round trip (ADR-0058). Go to the result page with an exchange ticket
    (the screen reads it from the frame URL and exchanges it).

    "Not signed in" and "not permitted" are not failures (it was only a try without a screen), so they are not
    logged as failures.
    """
    if query.error is not None or not query.code or not query.state:
        if query.error not in _SILENT_DECLINES:
            logger.warning("sso_renewal_failed: %s", query.error or "sso_callback_invalid")
            return _renewal_result(renewal.RenewalResult.FAILED)
        logger.info("sso_renewal_declined")
        return _renewal_result(renewal.RenewalResult.DECLINED)
    try:
        handoff = tools.login.execute(code=query.code, state=query.state, browser_binding=binding)
    except IdentityFederationError as error:
        logger.warning("sso_renewal_failed: %s", error.code)
        return _renewal_result(renewal.RenewalResult.FAILED)
    _log_account_changes(handoff.account)
    return _renewal_result(renewal.RenewalResult.RENEWED, handoff.ticket)


def _renewal_result(result: renewal.RenewalResult, ticket: str | None = None) -> RedirectResponse:
    """Go to the result page (drop the passphrase cookie and mark the response as frameable only by our own origin)."""
    response = _redirect(renewal.result_location(result, ticket))
    renewal.allow_same_origin_framing(response)
    return response


def _complete_link(callback: SsoCallback, tools: _CallbackTools) -> RedirectResponse:
    """Link the returning party to the user who started the round trip and go back to the settings screen.

    ⚠ **Do not re-decide by looking at the currently signed-in user.** Whom to link to was fixed when the round trip
    started (``link_user_id`` in the record). What is checked here is only "is that same person
    still signed in"; if someone else is, refuse.
    """
    viewer = tools.viewer
    if viewer is None:
        return _link_failed(SsoLinkSessionMismatchError.code)
    try:
        tools.link.execute(callback=callback, user_id=viewer.user_id)
    except IdentityFederationError as error:
        logger.warning("sso_link_failed: %s", error.code)
        return _link_failed(error.code)
    logger.info("sso_link_succeeded")
    return _redirect(f"{SECURITY_SCREEN}?sso_link=linked")


@router.post("/link/start", response_model=SsoLinkStartResponse)
def start_link(
    *,
    principal: Annotated[AuthenticatedPrincipal, Depends(get_person_principal)],
    use_case: Annotated[StartSsoLink, Depends(dependencies.start_sso_link)],
    response: Response,
) -> SsoLinkStartResponse:
    """Start a linking round trip. **The screen navigates to this URL itself** (ADR-0036).

    It is an XHR rather than returning 303 so that ⚠ **a 401 can be returned to a caller whose
    authentication has expired**. Starting with a navigation would, when expired, only show the
    raw JSON body, with no way offered to retry.

    ⚠ **CSRF protection applies here.** It is a cookie-authenticated mutation, so it is
    covered by ``CsrfMiddleware`` and cannot be triggered from other pages.
    """
    authorization = use_case.execute(user_id=principal.user_id)
    response.set_cookie(
        SSO_BINDING_COOKIE,
        authorization.browser_binding,
        max_age=settings.oidc_login_session_ttl_seconds,
        httponly=True,
        secure=settings.session_cookie_secure,
        samesite="lax",
        path=router.prefix,
    )
    return SsoLinkStartResponse(authorization_url=authorization.authorization_url)


@router.get("/link", response_model=FederatedLinkResponse)
def describe_link(
    *,
    principal: Annotated[AuthenticatedPrincipal, Depends(get_active_principal)],
    use_case: Annotated[DescribeFederatedLink, Depends(dependencies.describe_federated_link)],
    db: DbDep,
) -> FederatedLinkResponse:
    """Answer the state of one's own links (ADR-0036). Other people's are not visible."""
    link = use_case.execute(user_id=principal.user_id)
    return FederatedLinkResponse(
        available=link.available,
        display_name=link.display_name,
        linked=link.linked,
        linked_at=link.linked_at,
        can_unlink=link.linked and _has_other_entrance(db, principal.user_id),
    )


@router.delete("/link", response_model=StatusResponse)
def remove_link(
    *,
    principal: Annotated[AuthenticatedPrincipal, Depends(get_person_principal)],
    use_case: Annotated[UnlinkFederatedIdentity, Depends(dependencies.unlink_federated_identity)],
    db: DbDep,
) -> StatusResponse:
    """Remove a link. ⚠ **Refuses if the user could no longer sign in after removal** (ADR-0036)."""
    provider = dependencies.identity_provider()
    if provider is None:
        raise SsoNotConfiguredError
    use_case.execute(
        issuer=provider.issuer,
        user_id=principal.user_id,
        has_other_entrance=_has_other_entrance(db, principal.user_id),
    )
    logger.info("sso_identity_unlinked")
    return StatusResponse(status="ok")


def _has_other_entrance(db: Session, user_id: int) -> bool:
    """Whether this user still has **a way in** after the IdP is removed.

    ⚠ **Two-factor authentication is not a way in.** It is a second factor behind the password, so
    it cannot get anyone in by itself. What counts is passwords and passkeys.
    """
    user = db.get(User, user_id)
    if user is None:  # pragma: no cover - only if deleted right after passing authentication
        return False
    if user.has_local_password:
        return True
    return CountLocalFactors(SqlLocalFactorDirectory(db)).for_user(user_id).passkeys > 0


def _silently_declined(redirect_to: str) -> RedirectResponse:
    """Tried without a screen, but not signed in at the IdP (ADR-0052).

    **Not recorded as a failure.** Otherwise people who merely opened the login screen would pile up in the audit log.
    The destination (``redirect_to``) is carried back so that signing in again with the button also returns there.
    """
    logger.info("sso_silent_login_declined")
    query = urlencode({SILENT_DECLINED_PARAM: "declined", "redirect_to": redirect_to})
    return _redirect(f"{LOGIN_SCREEN}?{query}")


def _link_failed(code: str) -> RedirectResponse:
    """Return a linking failure to the settings screen.

    ⚠ **Do not go back to the login screen.** The person who pressed it is still signed in, so sending them
    to the login screen would mean "told to sign in again while already signed in".
    """
    safe = code if _ERROR_CODE.fullmatch(code) else _GENERIC_ERROR
    return _redirect(f"{SECURITY_SCREEN}?sso_link_error={safe}")


#: Local token the screen attaches when exchanging a continuing round trip's ticket (may be expired; ADR-0058)
_continued_bearer = HTTPBearer(auto_error=False)


def _continued_user(
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(_continued_bearer)] = None,
) -> int | None:
    """Whose login the local token attached by the screen was (``None`` if unreadable)."""
    if credentials is None or credentials.scheme.lower() != "bearer":
        return None
    return continued_user_of(credentials.credentials)


@router.post("/token", response_model=SsoSessionResponse)
def exchange_ticket(
    *,
    body: SsoTicketRequest,
    response: Response,
    db: DbDep,
    use_case: Annotated[ExchangeSsoTicket, Depends(dependencies.exchange_sso_ticket)],
    continued_user: Annotated[int | None, Depends(_continued_user)],
) -> SsoSessionResponse:
    """Exchange the ticket for tokens (one time only).

    The temporary password state (``must_change_password``) is not cleared by signing in via SSO.
    Silently dropping it here would make a temporary password issued by a parent meaningless (ADR-0011).

    Logins via SSO get no refresh token (ADR-0058). For a continuing round trip's ticket (``continuing``),
    ⚠ **do not exchange if it is a different person from the local token** (401 ``sso_renewal_switched_user``; they
    signed in again as someone else at the IdP, and the open screen belongs to the previous person). If the local token
    is unreadable, it enters as a new login.
    """
    session = use_case.execute(ticket=body.ticket)
    user = db.get(User, session.user_id)
    if user is None or not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={"error": "invalid_credentials"},
        )
    if body.continuing and continued_user is not None and continued_user != user.id:
        logger.info("sso_renewal_switched_user")
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail={"error": "sso_renewal_switched_user"})
    pair = TokenService.create_token_pair(user, federated_login=session.login)
    set_access_token_cookie(response, str(pair["access_token"]))
    logger.info("sso_renewal_succeeded" if body.continuing else "sso_login_succeeded")
    return SsoSessionResponse(
        access_token=str(pair["access_token"]),
        refresh_token=None,
        token_type=str(pair["token_type"]),
        expires_in=int(str(pair["expires_in"])),
        must_change_password=user.must_change_password,
        redirect_to=session.redirect_to,
    )


def _redirect(url: str) -> RedirectResponse:
    """Go back to the SPA. The passphrase cookie is dropped here (the round trip is over)."""
    response = RedirectResponse(url=url, status_code=status.HTTP_303_SEE_OTHER)
    response.delete_cookie(SSO_BINDING_COOKIE, path=router.prefix)
    return response


def _to_login_screen(code: str) -> RedirectResponse:
    safe = code if _ERROR_CODE.fullmatch(code) else _GENERIC_ERROR
    return _redirect(f"{LOGIN_SCREEN}?sso_error={safe}")


def _failed(reason: str) -> RedirectResponse:
    """Log the failure and go back to the login screen.

    Who tried is not written. It is unknown while the SSO login has not succeeded.
    """
    safe = reason if _ERROR_CODE.fullmatch(reason) else _GENERIC_ERROR
    logger.warning("sso_login_failed: %s", safe)
    return _to_login_screen(safe)


__all__ = ["HANDOFF_SCREEN", "LOGIN_SCREEN", "SILENT_DECLINED_PARAM", "SSO_BINDING_COOKIE", "router"]


# The notice body is a single ``application/x-www-form-urlencoded`` field. **Do not use
# ``Form()``** -- FastAPI's ``Form`` requires ``python-multipart``, which would add a dependency
# just for this one place.
#: Upper limit of the accepted body. It holds only one ``logout_token``, so this is ample.
_LOGOUT_BODY_MAX_BYTES = 16 * 1024


@router.post("/backchannel-logout", include_in_schema=False)
async def receive_backchannel_logout(
    request: Request,
    use_case: Annotated[ReceiveBackchannelLogout, Depends(dependencies.receive_backchannel_logout)],
) -> StatusResponse:
    """Receive revocation notices from the IdP (OpenID Connect Back-Channel Logout 1.0; ADR-0032).

    ⚠ **This endpoint can be called unauthenticated.** The only proof of the sender is the ``logout_token``
    signature, so anything failing verification is dropped with 400 without a reason (do not reveal how far it got).

    ⚠ **The response means only "received".** The session actually ends the next time
    that token is presented (the server keeps no session records).

    Verification makes synchronous HTTP calls for discovery and JWKS, so processing is offloaded to the thread pool
    (same reason ``/login`` and ``/callback`` are ``def``).
    """
    logout_token = _logout_token_of(await _bounded_body(request))
    notice = await run_in_threadpool(use_case.execute, logout_token=logout_token)
    logger.info(
        "sso_backchannel_logout_received: scope=%s",
        "session" if notice.session.session_id else "subject",
    )
    return StatusResponse(status="ok")


async def _bounded_body(request: Request) -> bytes:
    """Read the body. **Refuse oversized ones without reading** (the endpoint can be called unauthenticated)."""
    declared = request.headers.get("Content-Length")
    if declared is not None and declared.isdigit() and int(declared) > _LOGOUT_BODY_MAX_BYTES:
        raise InvalidLogoutTokenError
    body = await request.body()
    if len(body) > _LOGOUT_BODY_MAX_BYTES:
        raise InvalidLogoutTokenError
    return body


def _logout_token_of(body: bytes) -> str:
    """Extract ``logout_token=<JWT>``. Reject missing, empty or repeated ones."""
    values = [value for name, value in parse_qsl(body.decode("ascii", "replace")) if name == "logout_token"]
    if len(values) != 1 or not values[0]:
        raise InvalidLogoutTokenError
    return values[0]
