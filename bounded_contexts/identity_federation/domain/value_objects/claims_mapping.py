"""ID トークン（および UserInfo）のクレーム -> :class:`FederatedUser` の対応付け。

クレーム名は IdP ごとに違うため設定で変えられる（``OIDC_*_CLAIM``）。ここは
「どの名前から何を読むか」だけを持ち、通信は行わない（純粋な変換なので単体
テストで確かめられる）。
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any

from bounded_contexts.identity_federation.domain.exceptions import (
    InvalidIdTokenError,
    SsoEmailMissingError,
)
from bounded_contexts.identity_federation.domain.value_objects.federated_user import (
    FederatedUser,
)

# 表示名が対応付け先に無いときの代替。IdP の実装差を吸収する。
_DISPLAY_NAME_FALLBACK_CLAIMS = ("name", "preferred_username", "nickname")


@dataclass(frozen=True)
class ClaimsMapping:
    email_claim: str = "email"
    display_name_claim: str = "name"

    def apply(self, claims: Mapping[str, Any]) -> FederatedUser:
        """クレームを利用者の情報へ写す。

        ``sub`` が無いものは ID トークンとして成立していない。メールアドレスは
        既存の利用者と突き合わせる唯一の手掛かりなので、無ければ失敗として扱う。
        """
        subject = _text(claims.get("sub"))
        if not subject:
            raise InvalidIdTokenError
        email = _text(claims.get(self.email_claim))
        if not email:
            raise SsoEmailMissingError
        return FederatedUser(
            subject=subject,
            email=email.lower(),
            display_name=self._display_name(claims, email),
            email_verified=claims.get("email_verified") is True,
        )

    def _display_name(self, claims: Mapping[str, Any], email: str) -> str:
        """名乗り。対応付け先が空なら別名のクレーム、それも無ければメールの左側。"""
        for claim in (self.display_name_claim, *_DISPLAY_NAME_FALLBACK_CLAIMS):
            value = _text(claims.get(claim))
            if value:
                return value
        return email.partition("@")[0]


def _text(value: object) -> str:
    return value.strip() if isinstance(value, str) else ""


__all__ = ["ClaimsMapping"]
