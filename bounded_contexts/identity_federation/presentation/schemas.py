"""Pydantic schemas for SSO login."""

from __future__ import annotations

from pydantic import BaseModel, Field

from presentation.fastapi.schemas.auth import TokenResponse
from presentation.fastapi.schemas.types import UtcDatetime


class SsoProviderResponse(BaseModel):
    """What the login screen uses to decide whether to show the "sign in with SSO" button.

    It is readable unauthenticated, so endpoint URLs and the client ID are not included.
    """

    enabled: bool
    display_name: str


class SsoTicketRequest(BaseModel):
    """Exchange ticket handed over by the callback."""

    ticket: str = Field(min_length=1, max_length=255)
    #: Whether this is a ticket from a round trip continuing an expired login (hidden frame; ADR-0058).
    #: If true, exchange only when it is the same person as the local token sent along (which may be expired).
    continuing: bool = False


class SsoSessionResponse(TokenResponse):
    """Result of the exchange. ``redirect_to`` is the screen that started SSO (a route within the SPA)."""

    redirect_to: str


class FederatedLinkResponse(BaseModel):
    """The "your link status" shown on the settings screen (ADR-0036).

    ⚠ **The counterpart's ``subject`` is not included.** There is no point showing it, and including it would
    leak the IdP's internal identifier into browser history and logs.
    """

    #: Whether SSO itself is available. If false, the screen does not show this section.
    available: bool
    display_name: str = ""
    linked: bool = False
    linked_at: UtcDatetime | None = None
    #: Whether a way in remains after removal (ADR-0036). If false, the screen does not show the remove button.
    can_unlink: bool = False


class SsoLinkStartResponse(BaseModel):
    """Entry point of a linking round trip. The screen navigates to this URL **itself**.

    The server does not return 303 because this is an XHR -- if authentication has expired it can return
    401, and the screen can offer a retry.
    """

    authorization_url: str


__all__ = [
    "FederatedLinkResponse",
    "SsoLinkStartResponse",
    "SsoProviderResponse",
    "SsoSessionResponse",
    "SsoTicketRequest",
]
