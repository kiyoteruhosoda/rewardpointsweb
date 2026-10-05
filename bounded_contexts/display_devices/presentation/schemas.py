"""表示端末 API のリクエスト・レスポンス（ADR-0047）。"""

from __future__ import annotations

from pydantic import BaseModel, Field

from presentation.fastapi.schemas.types import UtcDatetime


class PairingStartRequest(BaseModel):
    #: 端末が開いている入口（``https://…``）。承認の画面を指す QR コードの宛先に使う。
    #: 省くと QR コードを返さない（確認コードを打てば承認できる）
    origin: str | None = Field(default=None, max_length=200, pattern=r"^https?://[^/\s#?]+$")


class PairingStartResponse(BaseModel):
    #: 画面に出す確認コード（``KQ7M-3XPA``）。運用管理者が承認の画面で打つ
    user_code: str
    #: 端末だけが知る秘密。受け取りに要る。画面には出さない
    device_code: str
    expires_in: int
    #: 受け取りを問い合わせる間隔（秒）
    interval: int
    #: 承認の画面（確認コード入り）を指す QR コード（SVG の data URI）。``origin`` を送らなければ ``None``
    qr_code: str | None = None


class PairingClaimRequest(BaseModel):
    device_code: str = Field(min_length=1, max_length=128)


class PairingClaimResponse(BaseModel):
    #: 端末の資格情報。``POST /api/display/session`` でアクセストークンに換える
    device_credential: str


class PairingApproveRequest(BaseModel):
    user_code: str = Field(min_length=1, max_length=32)
    family_id: int
    #: 端末の名前（例「リビング」）。家族の参加者一覧にもこの名前で並ぶ
    name: str = Field(min_length=1, max_length=100)


class DisplaySessionRequest(BaseModel):
    device_credential: str = Field(min_length=1, max_length=128)


class DisplaySessionResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    expires_in: int


class DisplayableFamilyResponse(BaseModel):
    id: int
    name: str


class DisplayDeviceResponse(BaseModel):
    account_id: int
    family_id: int
    family_name: str
    name: str
    created_at: UtcDatetime
    #: 最後にアクセストークンを取り直した日時。受け取る前なら ``None``
    last_used_at: UtcDatetime | None


__all__ = [
    "DisplayDeviceResponse",
    "DisplaySessionRequest",
    "DisplaySessionResponse",
    "DisplayableFamilyResponse",
    "PairingApproveRequest",
    "PairingClaimRequest",
    "PairingClaimResponse",
    "PairingStartRequest",
    "PairingStartResponse",
]
