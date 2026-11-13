"""Starting a link -- begin an IdP round trip for **a user who is already logged in** (ADR-0036).

The only difference from the login round trip is the content of the saved request; the authorization request sent to the IdP
is the same (only one redirect URI is registered). The saved request holds **the user who started it** (``link_user_id``)
.

⚠ **This is the crux of this round trip.** Without it, the return would be decided by looking at "who is signed in
now", and a browser that switched users mid-round-trip would link to **someone else's account**
.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import timedelta

from bounded_contexts.identity_federation.application.dto.sso_dto import (
    SsoAuthorizationDto,
)
from bounded_contexts.identity_federation.domain.entities.sso_login_session import (
    SsoLoginSession,
)
from bounded_contexts.identity_federation.domain.repositories.sso_login_session_repository import (
    SsoLoginSessionRepository,
)
from bounded_contexts.identity_federation.domain.services.login_secrets import (
    code_challenge_of,
    hash_secret,
    new_code_verifier,
    new_secret,
)
from bounded_contexts.identity_federation.domain.services.oidc_provider_gateway import (
    AuthorizationRequest,
    OidcProviderGateway,
)
from bounded_contexts.identity_federation.domain.value_objects.identity_provider import (
    IdentityProvider,
    require_usable,
)
from shared.kernel.timestamps import utcnow

#: Where to go after linking (the settings screen). Unlike login's ``redirect_to``,
#: there is no room for the user to choose -- it just returns to the screen where the button was pressed.
LINK_REDIRECT_TO = "/profile/security"


@dataclass(frozen=True)
class StartSsoLink:
    provider: IdentityProvider | None
    gateway: OidcProviderGateway
    sessions: SsoLoginSessionRepository
    session_ttl_seconds: int
    #: ``acr_values`` to put on the authorization request (empty = not requested). ADR-0039.
    acr_values: tuple[str, ...] = ()

    def execute(self, *, user_id: int) -> SsoAuthorizationDto:
        provider = require_usable(self.provider)
        state = new_secret()
        nonce = new_secret()
        code_verifier = new_code_verifier()
        binding = new_secret()
        self.sessions.issue(
            SsoLoginSession(
                state=state,
                nonce=nonce,
                code_verifier=code_verifier,
                binding_hash=hash_secret(binding),
                redirect_to=LINK_REDIRECT_TO,
                expires_at=utcnow() + timedelta(seconds=self.session_ttl_seconds),
                link_user_id=user_id,
            )
        )
        authorization_url = self.gateway.authorization_url(
            AuthorizationRequest(
                provider=provider,
                state=state,
                nonce=nonce,
                code_challenge=code_challenge_of(code_verifier),
                acr_values=self.acr_values,
            )
        )
        return SsoAuthorizationDto(authorization_url=authorization_url, browser_binding=binding)


__all__ = ["LINK_REDIRECT_TO", "StartSsoLink"]
