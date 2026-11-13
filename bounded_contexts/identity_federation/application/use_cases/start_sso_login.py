"""Starting an SSO login (building the authorization request and saving it).

``state`` / ``nonce`` / PKCE ``code_verifier`` are created here, the request is saved, and then
the URL to the IdP's authorization endpoint is returned. Without the saved request the return cannot be verified, so
**save first, then send out**.

The browser passphrase (``browser_binding``) is created along with it. The caller puts it in a cookie
and passes it back on return. The saved request holds only its hash.
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
from bounded_contexts.identity_federation.domain.value_objects.redirect_target import (
    RedirectTarget,
)
from shared.kernel.timestamps import utcnow


@dataclass(frozen=True)
class StartSsoLogin:
    provider: IdentityProvider | None
    gateway: OidcProviderGateway
    sessions: SsoLoginSessionRepository
    session_ttl_seconds: int
    #: ``acr_values`` to put on the authorization request (empty = not requested). ADR-0039.
    acr_values: tuple[str, ...] = ()

    def execute(self, *, redirect_to: str | None = None, silent: bool = False) -> SsoAuthorizationDto:
        """Return the URL to send to the IdP and the passphrase for the browser to hold.

        If ``silent``, the IdP is not allowed to show a screen (``prompt=none``. ADR-0052).
        """
        return self._start(redirect_to=RedirectTarget.parse(redirect_to).path, silent=silent, renewal=False)

    def renew(self) -> SsoAuthorizationDto:
        """A round trip that continues an expired login without showing a screen (inside a hidden frame. ADR-0058). Always ``prompt=none``."""
        return self._start(redirect_to="/", silent=True, renewal=True)

    def _start(self, *, redirect_to: str, silent: bool, renewal: bool) -> SsoAuthorizationDto:
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
                redirect_to=redirect_to,
                expires_at=utcnow() + timedelta(seconds=self.session_ttl_seconds),
                silent=silent,
                renewal=renewal,
            )
        )
        authorization_url = self.gateway.authorization_url(
            AuthorizationRequest(
                provider=provider,
                state=state,
                nonce=nonce,
                code_challenge=code_challenge_of(code_verifier),
                acr_values=self.acr_values,
                silent=silent,
            )
        )
        return SsoAuthorizationDto(authorization_url=authorization_url, browser_binding=binding)


__all__ = ["StartSsoLogin"]
