"""IdP の名乗りを、このアプリの利用者へ落とす。

順に、

1. ``(issuer, subject)`` の結び付きがあればその利用者
2. 無ければ**検証済みの**メールアドレスで既存の利用者へ寄せる

を試し、どちらでもなければログインを断る（``SsoAccountNotLinkedError``）。
**利用者は作らない**——SSO は既に居る人の入り口で、アカウントを増やす経路では
ない（ADR-0029）。結び付けた時点で ``federated_identities`` に控えを残すので、
2 回目以降は 1 で決まり、以後はメールアドレスを変えても入れる。
"""

from __future__ import annotations

from dataclasses import dataclass

from bounded_contexts.identity_federation.application.dto.sso_dto import (
    ResolvedAccountDto,
)
from bounded_contexts.identity_federation.domain.entities.federated_account import (
    FederatedAccount,
)
from bounded_contexts.identity_federation.domain.entities.federated_identity import (
    FederatedIdentity,
)
from bounded_contexts.identity_federation.domain.exceptions import (
    SsoAccountInactiveError,
    SsoAccountNotLinkedError,
)
from bounded_contexts.identity_federation.domain.repositories.federated_identity_repository import (
    FederatedIdentityRepository,
)
from bounded_contexts.identity_federation.domain.repositories.federated_user_directory import (
    FederatedUserDirectory,
)
from bounded_contexts.identity_federation.domain.value_objects.account_linking_policy import (
    AccountLinkingPolicy,
)
from bounded_contexts.identity_federation.domain.value_objects.federated_user import (
    FederatedUser,
)


@dataclass(frozen=True)
class ResolveFederatedAccount:
    identities: FederatedIdentityRepository
    directory: FederatedUserDirectory
    policy: AccountLinkingPolicy

    def execute(self, *, issuer: str, user: FederatedUser) -> ResolvedAccountDto:
        self.policy.ensure_accepted(user)
        known = self._known_account(issuer, user.subject)
        if known is not None:
            _ensure_active(known)
            return ResolvedAccountDto(user_id=known.user_id)
        return self._link_existing(issuer, user)

    def _known_account(self, issuer: str, subject: str) -> FederatedAccount | None:
        identity = self.identities.find(issuer, subject)
        if identity is None:
            return None
        account = self.directory.find_by_id(identity.user_id)
        if account is None:
            # 利用者が消されたのに結び付きだけ残っている。結び付け直しへ回す。
            return None
        self.identities.touch(identity)
        return account

    def _link_existing(self, issuer: str, user: FederatedUser) -> ResolvedAccountDto:
        """初めての相手。検証済みのメールアドレスが一致する利用者へ寄せる。"""
        if not self.policy.may_link(user):
            raise SsoAccountNotLinkedError
        existing = self.directory.find_by_email(user.email)
        if existing is None:
            raise SsoAccountNotLinkedError
        _ensure_active(existing)
        self.identities.link(FederatedIdentity(issuer=issuer, subject=user.subject, user_id=existing.user_id))
        return ResolvedAccountDto(user_id=existing.user_id, linked=True)


def _ensure_active(account: FederatedAccount) -> None:
    if not account.is_active:
        raise SsoAccountInactiveError


__all__ = ["ResolveFederatedAccount"]
