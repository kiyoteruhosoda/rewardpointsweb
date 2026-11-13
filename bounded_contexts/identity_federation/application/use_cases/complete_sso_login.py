"""Completing an SSO login (receive the return from the IdP and issue an exchange ticket).

Consume the saved request exactly once, **confirm the return comes from the browser we sent out**,
exchange the authorization code for verified claims, decide the user, and return a short-lived exchange ticket.
Tokens themselves are not issued here (issuing is done by
:class:`TokenService` in the presentation layer; exchanging the ticket for tokens is :class:`ExchangeSsoTicket`).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import timedelta

from bounded_contexts.identity_federation.application.dto.sso_dto import SsoHandoffDto
from bounded_contexts.identity_federation.application.use_cases.resolve_federated_account import (
    ResolveFederatedAccount,
)
from bounded_contexts.identity_federation.domain.entities.sso_login_ticket import (
    SsoLoginTicket,
)
from bounded_contexts.identity_federation.domain.exceptions import (
    SsoLoginSessionNotFoundError,
)
from bounded_contexts.identity_federation.domain.repositories.sso_login_session_repository import (
    SsoLoginSessionRepository,
)
from bounded_contexts.identity_federation.domain.repositories.sso_login_ticket_repository import (
    SsoLoginTicketRepository,
)
from bounded_contexts.identity_federation.domain.services.login_secrets import (
    hash_secret,
    new_secret,
)
from bounded_contexts.identity_federation.domain.services.oidc_provider_gateway import (
    CodeExchange,
    OidcProviderGateway,
)
from bounded_contexts.identity_federation.domain.value_objects.authentication_context import (
    RequestedAuthenticationContext,
)
from bounded_contexts.identity_federation.domain.value_objects.claims_mapping import (
    ClaimsMapping,
)
from bounded_contexts.identity_federation.domain.value_objects.federated_login import (
    FederatedLogin,
)
from bounded_contexts.identity_federation.domain.value_objects.federated_session import (
    FederatedSession,
)
from bounded_contexts.identity_federation.domain.value_objects.identity_provider import (
    IdentityProvider,
    require_usable,
)
from shared.kernel.timestamps import utcnow


@dataclass(frozen=True)
class CompleteSsoLogin:
    provider: IdentityProvider | None
    gateway: OidcProviderGateway
    sessions: SsoLoginSessionRepository
    tickets: SsoLoginTicketRepository
    claims: ClaimsMapping
    accounts: ResolveFederatedAccount
    ticket_ttl_seconds: int
    #: Matching the requested ``acr_values`` against the returned ``acr`` (ADR-0039).
    requested_context: RequestedAuthenticationContext = field(default_factory=RequestedAuthenticationContext)

    def execute(self, *, code: str, state: str, browser_binding: str | None) -> SsoHandoffDto:
        provider = require_usable(self.provider)
        session = self.sessions.consume(state)
        if not session.belongs_to(hash_secret(browser_binding or "")):
            # The return of an authorization request started in another browser (login CSRF). The saved request
            # is already consumed, so retrying with the same ``state`` is not possible.
            raise SsoLoginSessionNotFoundError
        claims = self.gateway.exchange_code(
            CodeExchange(
                provider=provider,
                code=code,
                code_verifier=session.code_verifier,
                nonce=session.nonce,
            )
        )
        # ⚠ **If requested, check it** (ADR-0039). Merely sending it guarantees nothing.
        self.requested_context.ensure_satisfied(claims.get("acr"))
        federated_user = self.claims.apply(claims)
        account = self.accounts.execute(issuer=provider.issuer, user=federated_user)
        ticket = new_secret()
        started_at = utcnow()
        self.tickets.issue(
            SsoLoginTicket(
                ticket_hash=hash_secret(ticket),
                user_id=account.user_id,
                redirect_to=session.redirect_to,
                expires_at=started_at + timedelta(seconds=self.ticket_ttl_seconds),
                login=FederatedLogin(
                    session=_federated_session(provider.issuer, federated_user.subject, claims.get("sid")),
                    started_at=started_at,
                ),
            )
        )
        return SsoHandoffDto(ticket=ticket, redirect_to=session.redirect_to, account=account)


def _federated_session(issuer: str, subject: str, sid: object) -> FederatedSession:
    """Map the ID token's ``sid`` to the target (ADR-0032).

    Some IdPs do not send ``sid``; if absent, proceed with ``None``
    (for that IdP, sessions can be stopped **only per user**).
    """
    session_id = sid.strip() if isinstance(sid, str) else ""
    return FederatedSession(issuer=issuer, subject=subject, session_id=session_id or None)


__all__ = ["CompleteSsoLogin"]
