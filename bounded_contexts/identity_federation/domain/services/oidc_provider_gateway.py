"""Interface for round trips with the OpenID Provider (implemented in the Infrastructure layer).

Protocol details (discovery, token endpoint, signature verification via JWKS) are
kept inside the implementation; the domain and application know only two things: "build the
authorization URL" and "exchange the authorization code for claims". What is returned is **verified**
claims, handled as a plain ``dict`` (HTTP and JWT library types are not brought inside).
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any, Protocol

from bounded_contexts.identity_federation.domain.value_objects.identity_provider import (
    IdentityProvider,
)


@dataclass(frozen=True)
class AuthorizationRequest:
    """Material for sending the browser to the IdP."""

    provider: IdentityProvider
    state: str
    nonce: str
    code_challenge: str
    #: Requested authentication strength (``acr_values``). Empty = not requested (ADR-0039).
    acr_values: tuple[str, ...] = ()
    #: Try without showing a screen (``prompt=none``; ADR-0052). If false, ``prompt`` is not added.
    silent: bool = False


@dataclass(frozen=True)
class LogoutTokenVerification:
    """Material for verifying a ``logout_token`` received from the IdP (ADR-0032)."""

    provider: IdentityProvider
    logout_token: str


@dataclass(frozen=True)
class CodeExchange:
    """Material for redeeming the returned authorization code."""

    provider: IdentityProvider
    code: str
    code_verifier: str
    nonce: str


class OidcProviderGateway(Protocol):
    def authorization_url(self, request: AuthorizationRequest) -> str:
        """Build the URL to the authorization endpoint.

        If the IdP cannot be reached, raises
        :class:`~bounded_contexts.identity_federation.domain.exceptions.IdentityProviderUnavailableError`.
        """

    def exchange_code(self, exchange: CodeExchange) -> Mapping[str, Any]:
        """Exchange the authorization code for verified claims.

        Returns only after checking the ID token's signature, issuer, audience and ``nonce``.
        Failures are ``InvalidIdTokenError`` / ``IdentityProviderUnavailableError``.
        """

    def verify_logout_token(self, verification: LogoutTokenVerification) -> Mapping[str, Any]:
        """Check the ``logout_token`` signature, issuer, audience and expiry, and return the claims.

        It uses the same key, issuer and audience as the ID token, so **this is as far as it can be
        checked as a JWT**. Deciding "it is a logout notice" is done by
        :class:`~bounded_contexts.identity_federation.domain.value_objects.logout_notice.LogoutNotice`
        Failures are ``InvalidLogoutTokenError`` / ``IdentityProviderUnavailableError``.
        """


__all__ = ["AuthorizationRequest", "CodeExchange", "OidcProviderGateway"]
