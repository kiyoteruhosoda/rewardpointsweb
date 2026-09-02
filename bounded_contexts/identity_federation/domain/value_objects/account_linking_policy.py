"""IdP が名乗った利用者を、このアプリの利用者へ結び付けてよいか。

**このアプリは SSO で利用者を作らない**（ADR-0029）。子どものアカウントは
メールアドレスを持たない（ADR-0011）ため、IdP の名乗りから作れる利用者は
そもそも一部に限られ、作れてしまうと親子関係のない宙に浮いたアカウントが増える。
入口は今までどおり管理画面と招待だけにし、SSO は**既に居る利用者への入り口**に
徹する。

そのため、ここが決めるのは「受け入れてよい相手か」と「既存の利用者へ寄せて
よいか」の 2 つだけになる。
"""

from __future__ import annotations

from dataclasses import dataclass

from bounded_contexts.identity_federation.domain.exceptions import (
    SsoEmailNotAllowedError,
)
from bounded_contexts.identity_federation.domain.value_objects.federated_user import (
    FederatedUser,
)


@dataclass(frozen=True)
class AccountLinkingPolicy:
    allowed_email_domains: tuple[str, ...] = ()

    def ensure_accepted(self, user: FederatedUser) -> None:
        """受け入れてよい相手かを確かめる。駄目なら :class:`SsoEmailNotAllowedError`。

        ドメインを絞っていない（空）なら誰でも受け入れる。IdP 側で対象を絞って
        いる構成が普通なので、既定はここで重ねて絞らない。
        """
        if not self.allowed_email_domains:
            return
        if user.email_domain not in {domain.lower().lstrip("@") for domain in self.allowed_email_domains}:
            raise SsoEmailNotAllowedError

    def may_link(self, user: FederatedUser) -> bool:
        """既存の利用者へ寄せてよいか。

        **検証済みのメールアドレスに限る。** IdP が検証していないアドレスで寄せると、
        相手のアドレスを名乗るだけで他人のアカウントへ入れてしまう。
        """
        return user.email_verified


__all__ = ["AccountLinkingPolicy"]
