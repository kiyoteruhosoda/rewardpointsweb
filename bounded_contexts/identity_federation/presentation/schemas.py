"""SSO ログインの Pydantic スキーマ。"""

from __future__ import annotations

from pydantic import BaseModel, Field

from presentation.fastapi.schemas.auth import TokenResponse
from presentation.fastapi.schemas.types import UtcDatetime


class SsoProviderResponse(BaseModel):
    """ログイン画面が「SSO で入る」ボタンを出すかどうかの判断材料。

    未認証で読めるため、接続先の URL やクライアント ID は載せない。
    """

    enabled: bool
    display_name: str


class SsoTicketRequest(BaseModel):
    """コールバックが渡した引き換え券。"""

    ticket: str = Field(min_length=1, max_length=255)


class SsoSessionResponse(TokenResponse):
    """引き換えの結果。``redirect_to`` は SSO を始めた画面（SPA 内の経路）。"""

    redirect_to: str


class FederatedLinkResponse(BaseModel):
    """設定画面に出す「自分の連携の状態」（ADR-0036）。

    ⚠ **相手の ``subject`` は載せない。** 画面に出す意味が無く、載せると
    IdP 側の内部の識別子がブラウザの履歴やログへ漏れていく。
    """

    #: SSO そのものが使えるか。偽なら画面はこの区画を出さない。
    available: bool
    display_name: str = ""
    linked: bool = False
    linked_at: UtcDatetime | None = None
    #: 外しても入り口が残るか（ADR-0036）。偽なら画面は解除のボタンを出さない。
    can_unlink: bool = False


class SsoLinkStartResponse(BaseModel):
    """連携の往復の入口。画面はこの URL へ**自分で**遷移する。

    サーバーが 303 で返さないのは、ここが XHR だから ——認証が切れていれば 401 を
    返せて、画面がやり直しを出せる。
    """

    authorization_url: str


__all__ = [
    "FederatedLinkResponse",
    "SsoLinkStartResponse",
    "SsoProviderResponse",
    "SsoSessionResponse",
    "SsoTicketRequest",
]
