"""Inputs and outputs of identity federation use cases (the presentation layer maps these to Pydantic)."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from bounded_contexts.identity_federation.domain.value_objects.federated_login import (
    FederatedLogin,
)


@dataclass(frozen=True)
class SsoProviderDto:
    """What decides whether the login screen shows a "Sign in with SSO" button."""

    enabled: bool
    display_name: str


@dataclass(frozen=True)
class SsoAuthorizationDto:
    """What is needed to send the browser to the IdP.

    ``browser_binding`` is a passphrase placed in the sending browser's cookie, used on return
    to check "is it the same browser" (stops login CSRF).
    """

    authorization_url: str
    browser_binding: str


@dataclass(frozen=True)
class ResolvedAccountDto:
    """Result of mapping the IdP's assertion to a user of this app.

    ``linked`` means "linked for the first time in this round trip" (used to tell log lines apart).
    From the second time on it is decided by ``(issuer, subject)``, so it is false. ``provisioned`` means
    "the linked account was created in this round trip" (ADR-0041).
    """

    user_id: int
    linked: bool = False
    provisioned: bool = False


@dataclass(frozen=True)
class SsoHandoffDto:
    """What the callback hands to the SPA (exchange ticket and return destination)."""

    ticket: str
    redirect_to: str
    account: ResolvedAccountDto


@dataclass(frozen=True)
class SsoSessionDto:
    """Login result taken out of the exchange ticket.

    ``login`` is stamped into the issued tokens (ADR-0032). Without it, even when a logout notice
    arrives **we cannot tell which tokens to invalidate**.
    """

    user_id: int
    redirect_to: str
    login: FederatedLogin


@dataclass(frozen=True)
class FederatedLinkDto:
    """"My federation status" shown on the settings screen (ADR-0036).

    If ``available`` is false, the screen does not show this section at all (SSO is disabled).
    """

    available: bool
    display_name: str = ""
    linked: bool = False
    linked_at: datetime | None = None


__all__ = [
    "FederatedLinkDto",
    "ResolvedAccountDto",
    "SsoAuthorizationDto",
    "SsoHandoffDto",
    "SsoProviderDto",
    "SsoSessionDto",
]
