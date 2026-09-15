"""連携の開始 ——**既にログインしている利用者**の IdP 往復を始める（ADR-0036）。

ログインの往復との違いは控えの中身だけで、IdP へ送る認可要求は同じものになる
（戻り先の URI も 1 つしか登録しない）。控えには **始めた本人**（``link_user_id``）を
入れる。

⚠ **これがこの往復の要である。** 入れておかないと、戻ってきたときに「いま入って
いる人」を見て決めることになり、往復の途中で入れ替わったブラウザが**別人の口座へ**
結び付ける。
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

#: 連携が終わったあとの戻り先（設定画面）。ログインの ``redirect_to`` と違い、
#: 利用者に選ばせる余地は無い ——押した画面へ返すだけである。
LINK_REDIRECT_TO = "/profile/security"


@dataclass(frozen=True)
class StartSsoLink:
    provider: IdentityProvider | None
    gateway: OidcProviderGateway
    sessions: SsoLoginSessionRepository
    session_ttl_seconds: int

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
            )
        )
        return SsoAuthorizationDto(authorization_url=authorization_url, browser_binding=binding)


__all__ = ["LINK_REDIRECT_TO", "StartSsoLink"]
