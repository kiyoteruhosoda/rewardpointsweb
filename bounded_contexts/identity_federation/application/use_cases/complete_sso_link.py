"""Completing a link -- link the returned ``(issuer, subject)`` to **the user who started the round trip**.

The difference from completing a login (:class:`CompleteSsoLogin`) is that it does **not look up**
the user. Who to link to was decided when the round trip started, and there is no room to decide again here
(ADR-0036).

There are 4 reasons to refuse.

- No saved request, or expired -- not a round trip we sent out
- Passphrase mismatch -- a round trip started in another browser (login CSRF)
- The user who started the round trip differs from the current session -- cannot decide whom to link
- That ``(issuer, subject)`` is linked to **another user** -- it would be a takeover
"""

from __future__ import annotations

from dataclasses import dataclass, field

from bounded_contexts.identity_federation.domain.entities.federated_identity import (
    FederatedIdentity,
)
from bounded_contexts.identity_federation.domain.exceptions import (
    SsoAlreadyLinkedError,
    SsoIdentityTakenError,
    SsoLinkSessionMismatchError,
    SsoLoginSessionNotFoundError,
)
from bounded_contexts.identity_federation.domain.repositories.federated_identity_repository import (
    FederatedIdentityRepository,
)
from bounded_contexts.identity_federation.domain.repositories.sso_login_session_repository import (
    SsoLoginSessionRepository,
)
from bounded_contexts.identity_federation.domain.services.login_secrets import hash_secret
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
from bounded_contexts.identity_federation.domain.value_objects.identity_provider import (
    IdentityProvider,
    require_usable,
)
from bounded_contexts.identity_federation.domain.value_objects.sso_callback import (
    SsoCallback,
)


@dataclass(frozen=True)
class CompleteSsoLink:
    provider: IdentityProvider | None
    gateway: OidcProviderGateway
    sessions: SsoLoginSessionRepository
    identities: FederatedIdentityRepository
    claims: ClaimsMapping
    #: Matching the requested ``acr_values`` against the returned ``acr`` (ADR-0039).
    requested_context: RequestedAuthenticationContext = field(default_factory=RequestedAuthenticationContext)

    def execute(self, *, callback: SsoCallback, user_id: int) -> FederatedIdentity:
        provider = require_usable(self.provider)
        session = self.sessions.consume(callback.state)
        if not session.belongs_to(hash_secret(callback.browser_binding or "")):
            raise SsoLoginSessionNotFoundError
        if not session.started_by(user_id):
            # ⚠ Signed out mid-round-trip, or signed in again as another user. **Do not re-link
            #   to the current session** -- an entrance would appear on an account other than the one who started it.
            raise SsoLinkSessionMismatchError
        claims = self.gateway.exchange_code(
            CodeExchange(
                provider=provider,
                code=callback.code,
                code_verifier=session.code_verifier,
                nonce=session.nonce,
            )
        )
        # ⚠ **Check it for linking too** (ADR-0039). If this were let through, a round trip that
        #   passed with weak authentication would directly become a new entrance.
        self.requested_context.ensure_satisfied(claims.get("acr"))
        subject = self.claims.apply(claims).subject
        self._ensure_free(provider.issuer, subject, user_id)
        return self.identities.link(FederatedIdentity(issuer=provider.issuer, subject=subject, user_id=user_id))

    def _ensure_free(self, issuer: str, subject: str, user_id: int) -> None:
        taken = self.identities.find(issuer, subject)
        if taken is not None and taken.user_id != user_id:
            raise SsoIdentityTakenError
        mine = self.identities.find_for_user(issuer, user_id)
        if mine is not None and mine.subject != subject:
            # Do not silently allow a replacement, since the route that used the previous link would disappear.
            raise SsoAlreadyLinkedError


__all__ = ["CompleteSsoLink"]
