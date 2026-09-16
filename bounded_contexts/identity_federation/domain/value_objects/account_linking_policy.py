"""IdP が名乗った利用者を、このアプリの利用者へ結び付けてよいか。

ここが決めるのは「受け入れてよい相手か」と「既存の利用者へ寄せてよいか」の 2 つだけ。
寄せる先が無い初めての相手は口座を作って迎える（ADR-0041）が、**誰に作ってよいかは
ここでは決めない** ——assay のアプリの割り当てが決めていて、割り当てが無い人は
code を持って戻ってこない。
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
    #: ⚠ **既定は寄せない**（ADR-0033）。条件の ``email_verified`` は、assay では
    #: 「テナント管理者がそう主張している」であって本人の証明ではない。
    #: ⚠ 閉じていても、**同じメールアドレスの口座があれば作らずに断る**（ADR-0041）。
    #: 本人がその口座へ入って結び付ける（ADR-0036）。
    link_by_email: bool = False
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

        **既定は寄せない**（ADR-0033）。開けたときも**検証済みのメールアドレスに
        限る** ——IdP が検証していないアドレスで寄せると、相手のアドレスを名乗るだけで
        他人のアカウントへ入れてしまう。

        ⚠ **``email_verified`` の意味は IdP ごとに違う。** 自前 idp (assay) では
        この値が真になる経路は自己登録の確認メールだけで、**管理者によるメール変更は
        この値を維持する**。つまり「本人が所有を証明した」ではなく
        **「テナント管理者がそう主張している」**である。開けるなら、つないだ IdP で
        この値がどう立つのかまで確かめること。
        """
        return self.link_by_email and user.email_verified


__all__ = ["AccountLinkingPolicy"]
