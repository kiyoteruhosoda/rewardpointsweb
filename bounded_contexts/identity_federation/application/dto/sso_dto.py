"""ID 連携ユースケースの入出力（Presentation 層はこれを Pydantic へ写す）。"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from bounded_contexts.identity_federation.domain.value_objects.federated_login import (
    FederatedLogin,
)


@dataclass(frozen=True)
class SsoProviderDto:
    """ログイン画面に「SSO で入る」ボタンを出すかどうかの判断材料。"""

    enabled: bool
    display_name: str


@dataclass(frozen=True)
class SsoAuthorizationDto:
    """IdP へ送り出すための材料。

    ``browser_binding`` は送り出したブラウザの Cookie へ置く合言葉で、戻ってきた
    ときに「同じブラウザか」を確かめるために使う（ログイン CSRF を止める）。
    """

    authorization_url: str
    browser_binding: str


@dataclass(frozen=True)
class ResolvedAccountDto:
    """IdP の名乗りを、このアプリの利用者へ落とした結果。

    ``linked`` は「この往復で初めて結び付いた」ことを示す（ログの区別に使う）。
    2 回目以降は ``(issuer, subject)`` で決まるので偽になる。``provisioned`` は
    「結び付けた口座を、この往復で作った」（ADR-0041）。
    """

    user_id: int
    linked: bool = False
    provisioned: bool = False


@dataclass(frozen=True)
class SsoHandoffDto:
    """コールバックが SPA へ渡すもの（引き換え券と戻り先）。"""

    ticket: str
    redirect_to: str
    account: ResolvedAccountDto


@dataclass(frozen=True)
class SsoSessionDto:
    """引き換え券から取り出したログイン結果。

    ``login`` は発行するトークンへ刻む（ADR-0032）。刻んでおかないと、停止の通知が
    届いても**どのトークンを無効にすればよいかが分からない**。
    """

    user_id: int
    redirect_to: str
    login: FederatedLogin


@dataclass(frozen=True)
class FederatedLinkDto:
    """設定画面に出す「自分の連携の状態」（ADR-0036）。

    ``available`` が偽なら、画面はこの区画そのものを出さない（SSO が無効）。
    """

    available: bool
    display_name: str = ""
    linked: bool = False
    linked_at: datetime | None = None


__all__ = [
    "FederatedLinkDto",
    "ResolvedAccountDto",
    "SsoAuthorizationDto",
    "SsoHandoffDto",
    "SsoProviderDto",
    "SsoSessionDto",
]
