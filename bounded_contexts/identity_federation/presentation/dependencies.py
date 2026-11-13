"""Assembly of use cases (factories for ``Depends()``).

Only this module builds value objects from settings (``OIDC_*`` in ``settings``).
Use cases receive already-built :class:`IdentityProvider` and the like.

IdP metadata (discovery, JWKS) is cached in-process, so the gateway is
**a single reused instance**. Tests substitute it with
``app.dependency_overrides[dependencies.oidc_gateway]``.
"""

from __future__ import annotations

from typing import Annotated

from fastapi import Depends
from sqlalchemy.orm import Session

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
from bounded_contexts.identity_federation.application.use_cases.resolve_federated_account import (
    ResolveFederatedAccount,
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
from bounded_contexts.identity_federation.domain.services.oidc_provider_gateway import (
    OidcProviderGateway,
)
from bounded_contexts.identity_federation.domain.value_objects.account_linking_policy import (
    AccountLinkingPolicy,
)
from bounded_contexts.identity_federation.domain.value_objects.authentication_context import (
    RequestedAuthenticationContext,
)
from bounded_contexts.identity_federation.domain.value_objects.claims_mapping import (
    ClaimsMapping,
)
from bounded_contexts.identity_federation.domain.value_objects.client_credential import (
    ClientCredential,
)
from bounded_contexts.identity_federation.domain.value_objects.identity_provider import (
    IdentityProvider,
)
from bounded_contexts.identity_federation.infrastructure.httpx_oidc_provider_gateway import (
    HttpxOidcProviderGateway,
)
from bounded_contexts.identity_federation.infrastructure.sql_federated_identity_repository import (
    SqlFederatedIdentityRepository,
)
from bounded_contexts.identity_federation.infrastructure.sql_federated_user_directory import (
    SqlFederatedUserDirectory,
)
from bounded_contexts.identity_federation.infrastructure.sql_session_revocation_repository import (
    SqlSessionRevocationRepository,
)
from bounded_contexts.identity_federation.infrastructure.sql_sso_login_session_repository import (
    SqlSsoLoginSessionRepository,
)
from bounded_contexts.identity_federation.infrastructure.sql_sso_login_ticket_repository import (
    SqlSsoLoginTicketRepository,
)
from shared.kernel.database.session import get_db
from shared.kernel.settings.settings import settings

DbDep = Annotated[Session, Depends(get_db)]

_gateway = HttpxOidcProviderGateway()


def oidc_gateway() -> OidcProviderGateway:
    return _gateway


GatewayDep = Annotated[OidcProviderGateway, Depends(oidc_gateway)]


def client_credential() -> ClientCredential:
    """Build the means of identifying to the token endpoint from settings."""
    return ClientCredential(
        method=settings.oidc_client_auth_method,
        secret=settings.oidc_client_secret,
        private_key_file=settings.oidc_private_key_file,
        private_key_kid=settings.oidc_private_key_kid,
    )


def identity_provider() -> IdentityProvider | None:
    """Build the federation target from settings. ``None`` if disabled."""
    if not settings.oidc_enabled:
        return None
    return IdentityProvider(
        display_name=settings.oidc_display_name,
        issuer=settings.oidc_issuer,
        client_id=settings.oidc_client_id,
        credential=client_credential(),
        redirect_uri=settings.oidc_redirect_uri,
        scopes=tuple(settings.oidc_scopes),
    )


def claims_mapping() -> ClaimsMapping:
    return ClaimsMapping(
        email_claim=settings.oidc_email_claim,
        display_name_claim=settings.oidc_display_name_claim,
    )


def requested_authentication_context() -> RequestedAuthenticationContext:
    """Matching of the requested authentication strength (ADR-0039). Empty = not requested."""
    return RequestedAuthenticationContext(values=tuple(settings.oidc_acr_values))


def account_linking_policy() -> AccountLinkingPolicy:
    return AccountLinkingPolicy(
        link_by_email=settings.oidc_link_by_email,
        allowed_email_domains=tuple(settings.oidc_allowed_email_domains),
    )


def describe_sso_provider() -> DescribeSsoProvider:
    return DescribeSsoProvider(provider=identity_provider())


def start_sso_login(db: DbDep, gateway: GatewayDep) -> StartSsoLogin:
    return StartSsoLogin(
        provider=identity_provider(),
        gateway=gateway,
        sessions=SqlSsoLoginSessionRepository(db),
        session_ttl_seconds=settings.oidc_login_session_ttl_seconds,
        acr_values=tuple(settings.oidc_acr_values),
    )


def start_sso_link(db: DbDep, gateway: GatewayDep) -> StartSsoLink:
    """Start of a linking round trip (ADR-0036). The record lifetime is the same as for login."""
    return StartSsoLink(
        provider=identity_provider(),
        gateway=gateway,
        sessions=SqlSsoLoginSessionRepository(db),
        session_ttl_seconds=settings.oidc_login_session_ttl_seconds,
        acr_values=tuple(settings.oidc_acr_values),
    )


def complete_sso_link(db: DbDep, gateway: GatewayDep) -> CompleteSsoLink:
    return CompleteSsoLink(
        provider=identity_provider(),
        gateway=gateway,
        sessions=SqlSsoLoginSessionRepository(db),
        identities=SqlFederatedIdentityRepository(db),
        claims=claims_mapping(),
        requested_context=requested_authentication_context(),
    )


def describe_round_trip(db: DbDep) -> DescribeRoundTrip:
    return DescribeRoundTrip(sessions=SqlSsoLoginSessionRepository(db))


def describe_federated_link(db: DbDep) -> DescribeFederatedLink:
    return DescribeFederatedLink(
        identities=SqlFederatedIdentityRepository(db),
        provider=identity_provider(),
    )


def unlink_federated_identity(db: DbDep) -> UnlinkFederatedIdentity:
    return UnlinkFederatedIdentity(identities=SqlFederatedIdentityRepository(db))


def resolve_federated_account(db: DbDep) -> ResolveFederatedAccount:
    return ResolveFederatedAccount(
        identities=SqlFederatedIdentityRepository(db),
        directory=SqlFederatedUserDirectory(db),
        policy=account_linking_policy(),
    )


def complete_sso_login(db: DbDep, gateway: GatewayDep) -> CompleteSsoLogin:
    return CompleteSsoLogin(
        provider=identity_provider(),
        gateway=gateway,
        sessions=SqlSsoLoginSessionRepository(db),
        tickets=SqlSsoLoginTicketRepository(db),
        claims=claims_mapping(),
        accounts=resolve_federated_account(db),
        ticket_ttl_seconds=settings.oidc_login_ticket_ttl_seconds,
        requested_context=requested_authentication_context(),
    )


def exchange_sso_ticket(db: DbDep) -> ExchangeSsoTicket:
    return ExchangeSsoTicket(tickets=SqlSsoLoginTicketRepository(db))


def receive_backchannel_logout(db: DbDep, gateway: GatewayDep) -> ReceiveBackchannelLogout:
    """Receiver for revocation propagation (ADR-0032).

    Records are kept for **the refresh token lifetime**. Past that, tokens issued before the
    stop expire on their own.
    Logins via SSO hold no refresh credential (ADR-0058), so it is never shorter than **the access token lifetime**.
    """
    return ReceiveBackchannelLogout(
        provider=identity_provider(),
        gateway=gateway,
        revocations=SqlSessionRevocationRepository(db),
        keep_for_seconds=max(settings.refresh_token_expires_seconds, settings.access_token_expires_seconds),
    )


__all__ = [
    "DbDep",
    "GatewayDep",
    "account_linking_policy",
    "claims_mapping",
    "client_credential",
    "complete_sso_link",
    "complete_sso_login",
    "describe_federated_link",
    "describe_round_trip",
    "describe_sso_provider",
    "exchange_sso_ticket",
    "identity_provider",
    "oidc_gateway",
    "receive_backchannel_logout",
    "requested_authentication_context",
    "resolve_federated_account",
    "start_sso_link",
    "start_sso_login",
    "unlink_federated_identity",
]
