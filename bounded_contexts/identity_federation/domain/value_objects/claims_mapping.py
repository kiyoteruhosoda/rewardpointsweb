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

        ``sub`` が無いものは ID トークンとして成立していない。

        ⚠ **メールアドレスが無くても通す**（ADR-0038）。結び付きの鍵は ``sub`` なので、
        既に結び付いている相手はメールが無くても入れる。**無いと困る場面で断る**
        ——初回に既存の利用者を探すときだけである。
        """
        subject = _text(claims.get("sub"))
        if not subject:
            raise InvalidIdTokenError
        email = _text(claims.get(self.email_claim))
        return FederatedUser(
            subject=subject,
            email=email.lower() if email else None,
            display_name=self._display_name(claims, email, subject),
            email_verified=claims.get("email_verified") is True,
            # ⚠ **クレーム名は設定にしない。** OIDC Core の標準クレームで、口座を作るときの
            #   ``username`` の元になる（ADR-0041）。読み替えられると、作る口座の識別子が
            #   設定 1 つで変わる。
            preferred_username=_text(claims.get("preferred_username")) or None,
        )

    def _display_name(self, claims: Mapping[str, Any], email: str, subject: str) -> str:
        """名乗り。対応付け先が空なら別名のクレーム、それも無ければメールの左側。

        ⚠ **メールも無ければ ``sub`` を使う。** 読みにくい値になるが、**名乗りの
        空いた利用者を作るよりはよい** ——後から画面で直せる。
        """
        for claim in (self.display_name_claim, *_DISPLAY_NAME_FALLBACK_CLAIMS):
            value = _text(claims.get(claim))
            if value:
                return value
        return email.partition("@")[0] if email else subject


def _text(value: object) -> str:
    return value.strip() if isinstance(value, str) else ""


__all__ = ["ClaimsMapping"]
