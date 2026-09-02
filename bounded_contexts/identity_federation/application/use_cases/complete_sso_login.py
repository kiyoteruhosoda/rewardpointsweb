"""SSO ログインの完了（IdP からの戻りを受け取り、引き換え券を発行する）。

控えを 1 回限りで消費し、**送り出したブラウザからの戻りであることを確かめ**、
認可コードを検証済みのクレームへ換え、利用者を決めてから短命の引き換え券を返す。
トークンそのものはここでは発行しない（発行は Presentation 層の
:class:`TokenService`。券をトークンへ換えるのは :class:`ExchangeSsoTicket`）。
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import timedelta

from bounded_contexts.identity_federation.application.dto.sso_dto import SsoHandoffDto
from bounded_contexts.identity_federation.application.use_cases.resolve_federated_account import (
    ResolveFederatedAccount,
)
from bounded_contexts.identity_federation.domain.entities.sso_login_ticket import (
    SsoLoginTicket,
)
from bounded_contexts.identity_federation.domain.exceptions import (
    SsoLoginSessionNotFoundError,
)
from bounded_contexts.identity_federation.domain.repositories.sso_login_session_repository import (
    SsoLoginSessionRepository,
)
from bounded_contexts.identity_federation.domain.repositories.sso_login_ticket_repository import (
    SsoLoginTicketRepository,
)
from bounded_contexts.identity_federation.domain.services.login_secrets import (
    hash_secret,
    new_secret,
)
from bounded_contexts.identity_federation.domain.services.oidc_provider_gateway import (
    CodeExchange,
    OidcProviderGateway,
)
from bounded_contexts.identity_federation.domain.value_objects.claims_mapping import (
    ClaimsMapping,
)
from bounded_contexts.identity_federation.domain.value_objects.identity_provider import (
    IdentityProvider,
    require_usable,
)
from shared.kernel.timestamps import utcnow


@dataclass(frozen=True)
class CompleteSsoLogin:
    provider: IdentityProvider | None
    gateway: OidcProviderGateway
    sessions: SsoLoginSessionRepository
    tickets: SsoLoginTicketRepository
    claims: ClaimsMapping
    accounts: ResolveFederatedAccount
    ticket_ttl_seconds: int

    def execute(self, *, code: str, state: str, browser_binding: str | None) -> SsoHandoffDto:
        provider = require_usable(self.provider)
        session = self.sessions.consume(state)
        if not session.belongs_to(hash_secret(browser_binding or "")):
            # 別のブラウザで始められた認可要求の戻り（ログイン CSRF）。控えは
            # 消費済みなので、同じ ``state`` で再挑戦することはできない。
            raise SsoLoginSessionNotFoundError
        claims = self.gateway.exchange_code(
            CodeExchange(
                provider=provider,
                code=code,
                code_verifier=session.code_verifier,
                nonce=session.nonce,
            )
        )
        account = self.accounts.execute(issuer=provider.issuer, user=self.claims.apply(claims))
        ticket = new_secret()
        self.tickets.issue(
            SsoLoginTicket(
                ticket_hash=hash_secret(ticket),
                user_id=account.user_id,
                redirect_to=session.redirect_to,
                expires_at=utcnow() + timedelta(seconds=self.ticket_ttl_seconds),
            )
        )
        return SsoHandoffDto(ticket=ticket, redirect_to=session.redirect_to, account=account)


__all__ = ["CompleteSsoLogin"]
