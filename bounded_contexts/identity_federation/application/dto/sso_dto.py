"""ID 連携ユースケースの入出力（Presentation 層はこれを Pydantic へ写す）。"""

from __future__ import annotations

from dataclasses import dataclass


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
    2 回目以降は ``(issuer, subject)`` で決まるので偽になる。
    """

    user_id: int
    linked: bool = False


@dataclass(frozen=True)
class SsoHandoffDto:
    """コールバックが SPA へ渡すもの（引き換え券と戻り先）。"""

    ticket: str
    redirect_to: str
    account: ResolvedAccountDto


@dataclass(frozen=True)
class SsoSessionDto:
    """引き換え券から取り出したログイン結果。"""

    user_id: int
    redirect_to: str


__all__ = [
    "ResolvedAccountDto",
    "SsoAuthorizationDto",
    "SsoHandoffDto",
    "SsoProviderDto",
    "SsoSessionDto",
]
