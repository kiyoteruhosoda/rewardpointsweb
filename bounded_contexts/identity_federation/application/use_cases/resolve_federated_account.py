"""IdP の名乗りを、このアプリの利用者へ落とす。

順に、

1. ``(issuer, subject)`` の結び付きがあればその利用者
2. 無ければ**検証済みの**メールアドレスで既存の利用者へ寄せる（既定は寄せない。ADR-0033）
3. どちらでもなければ**口座を作る**（ADR-0041）

を試す。3 で作るのは、**assay から code を持って戻ってきた相手＝このアプリの利用を
割り当てられた人**だからである。割り当てが無い人は assay の画面で止まり、ここまで
来ない（idp の ADR-0054）。結び付けた時点で ``federated_identities`` に控えを残すので、
2 回目以降は 1 で決まる。

⚠ **作れないときは断る。** 同じメールアドレスの口座が既にある（``sso_account_not_linked``）、
``username`` を決められない（``sso_username_unavailable``）。どちらも黙って別の値で
作ると、同じ人の口座が 2 つになるか、本人の知らない識別子になる。
"""

from __future__ import annotations

import logging
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
    SsoUsernameUnavailableError,
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
from shared.domain.auth.username import Username

logger = logging.getLogger(__name__)


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
            # ⚠ **写しは IdP を正とする**（ADR-0038）。ここで上書きしないと、
            #   向こうで改名・メール変更をしても表示が永久に古いままになる。
            self.directory.refresh_profile(known.user_id, email=user.email, display_name=user.display_name)
            return ResolvedAccountDto(user_id=known.user_id)
        return self._welcome(issuer, user)

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

    def _welcome(self, issuer: str, user: FederatedUser) -> ResolvedAccountDto:
        """初めての相手。寄せられる口座があれば寄せ、無ければ作る（ADR-0041）。

        ⚠ **メールアドレスが要るのはここだけである**（ADR-0038）。既に結び付いて
        いる相手は ``sub`` で引けるので、無くても入れる。
        """
        existing = self.directory.find_by_email(user.email) if user.email else None
        if existing is not None:
            if not self.policy.may_link(user):
                # ⚠ **作らずに断る**（ADR-0041）。作ると同じ人の口座が 2 つになる。寄せる
                #   設定は既定で閉じている（ADR-0033）ので、本人がその口座へ入って結び付ける。
                raise SsoAccountNotLinkedError
            _ensure_active(existing)
            return self._link(issuer, user.subject, existing, provisioned=False)
        username = self._free_username(user)
        created = self.directory.provision(username=username, email=user.email, display_name=user.display_name)
        if created is None:
            # 確かめてから作るまでのあいだに、同じ値を別の往復が取った。
            logger.warning("sso_username_unavailable", extra={"reason": "raced"})
            raise SsoUsernameUnavailableError
        return self._link(issuer, user.subject, created, provisioned=True)

    def _free_username(self, user: FederatedUser) -> str:
        """IdP の ``preferred_username`` を、このアプリの ``username`` にする。

        ⚠ **使えなければ断る。黙って連番や別の値を付けない**（ADR-0041）。ログには
        理由の区別だけを残し、値そのもの（PII）は残さない。
        """
        if user.preferred_username is None:
            logger.warning("sso_username_unavailable", extra={"reason": "missing"})
            raise SsoUsernameUnavailableError
        try:
            username = Username(user.preferred_username).value
        except ValueError as error:
            logger.warning("sso_username_unavailable", extra={"reason": "invalid"})
            raise SsoUsernameUnavailableError from error
        if self.directory.find_by_username(username) is not None:
            logger.warning("sso_username_unavailable", extra={"reason": "taken"})
            raise SsoUsernameUnavailableError
        return username

    def _link(self, issuer: str, subject: str, account: FederatedAccount, *, provisioned: bool) -> ResolvedAccountDto:
        self.identities.link(FederatedIdentity(issuer=issuer, subject=subject, user_id=account.user_id))
        return ResolvedAccountDto(user_id=account.user_id, linked=True, provisioned=provisioned)


def _ensure_active(account: FederatedAccount) -> None:
    if not account.is_active:
        raise SsoAccountInactiveError


__all__ = ["ResolveFederatedAccount"]
