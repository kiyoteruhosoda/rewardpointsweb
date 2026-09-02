"""SSO ログインの開始（認可要求の組み立てと控えの保存）。

``state`` / ``nonce`` / PKCE の ``code_verifier`` をここで作り、控えを残してから
IdP の認可エンドポイントへの URL を返す。控えが無ければ戻りを検証できないため、
**保存してから送り出す**。

ブラウザの合言葉（``browser_binding``）も一緒に作る。呼び出し側はこれを Cookie へ
置き、戻ってきたときに渡す。控えはハッシュだけを持つ。
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

    def execute(self, *, redirect_to: str | None = None) -> SsoAuthorizationDto:
        """IdP へ送り出す URL と、ブラウザへ持たせる合言葉を返す。"""
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
                redirect_to=RedirectTarget.parse(redirect_to).path,
                expires_at=utcnow() + timedelta(seconds=self.session_ttl_seconds),
            )
        )
        authorization_url = self.gateway.authorization_url(
            AuthorizationRequest(
                provider=provider,
                state=state,
                nonce=nonce,
                code_challenge=code_challenge_of(code_verifier),
            )
        )
        return SsoAuthorizationDto(authorization_url=authorization_url, browser_binding=binding)


__all__ = ["StartSsoLogin"]
