"""Receive a logout notice from the IdP (OpenID Connect Back-Channel Logout 1.0. ADR-0032).

This endpoint is **not called from the user's browser**. It is a server-to-server route that the IdP's
server calls directly, and the signature of the received ``logout_token`` is the only proof of the caller.

It does only one thing -- record "this session may no longer be used".
The session itself is a JWT with no server-side record, so there is nothing to drop here
(whether it is invalid is checked the next time the token is presented).
"""

from __future__ import annotations

from dataclasses import dataclass

from bounded_contexts.identity_federation.domain.entities.session_revocation import (
    SessionRevocation,
)
from bounded_contexts.identity_federation.domain.repositories.session_revocation_repository import (
    SessionRevocationRepository,
)
from bounded_contexts.identity_federation.domain.services.oidc_provider_gateway import (
    LogoutTokenVerification,
    OidcProviderGateway,
)
from bounded_contexts.identity_federation.domain.value_objects.identity_provider import (
    IdentityProvider,
    require_usable,
)
from bounded_contexts.identity_federation.domain.value_objects.logout_notice import (
    LogoutNotice,
)
from shared.kernel.timestamps import utcnow


@dataclass(frozen=True)
class ReceiveBackchannelLogout:
    provider: IdentityProvider | None
    gateway: OidcProviderGateway
    revocations: SessionRevocationRepository
    #: Seconds to keep the record. Pass **the refresh token lifetime** -- after that,
    #: tokens issued before the record expire on their own, and keeping the row is pointless.
    keep_for_seconds: int

    def execute(self, *, logout_token: str) -> LogoutNotice:
        provider = require_usable(self.provider)
        claims = self.gateway.verify_logout_token(LogoutTokenVerification(provider=provider, logout_token=logout_token))
        notice = LogoutNotice.from_claims(claims, issuer=provider.issuer)
        self.revocations.record(SessionRevocation.of(notice, now=utcnow(), keep_for_seconds=self.keep_for_seconds))
        return notice


__all__ = ["ReceiveBackchannelLogout"]
