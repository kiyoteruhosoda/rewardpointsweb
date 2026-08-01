"""認証系の Pydantic スキーマ。

ログインの識別子は ``username``。メールアドレスは任意項目なので、識別子には
使えない（ADR-0011）。
"""

from __future__ import annotations

from pydantic import BaseModel, EmailStr, Field, field_validator

from shared.domain.auth.username import MAX_LENGTH as USERNAME_MAX_LENGTH

DISPLAY_NAME_MAX_LENGTH = 100


class LoginRequest(BaseModel):
    username: str = Field(min_length=1, max_length=USERNAME_MAX_LENGTH)
    password: str
    # 二要素認証が有効なアカウントでのみ必須（未提示なら totp_required を返す）
    totp_code: str | None = None


class TokenResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str
    expires_in: int
    # 一時パスワードでのログイン。画面はパスワード変更へ誘導する（ADR-0011）
    must_change_password: bool = False


class RefreshRequest(BaseModel):
    refresh_token: str


class MeResponse(BaseModel):
    user_id: int
    username: str
    display_name: str
    email: str | None
    scopes: list[str]
    must_change_password: bool


class ProfileUpdateRequest(BaseModel):
    """表示名とメールアドレスの変更。

    ``email`` に ``null`` を送るとメールアドレスを外す。省略した場合は現状の
    まま（「``null`` を送った」と「送らなかった」は ``model_fields_set`` で
    区別する）。
    """

    display_name: str | None = Field(default=None, min_length=1, max_length=DISPLAY_NAME_MAX_LENGTH)
    email: EmailStr | None = None

    @field_validator("display_name")
    @classmethod
    def _strip(cls, value: str | None) -> str | None:
        if value is None:
            return None
        stripped = value.strip()
        if not stripped:
            raise ValueError("must not be blank")
        return stripped


class ChangePasswordRequest(BaseModel):
    current_password: str
    new_password: str = Field(min_length=8)


class ForgotPasswordRequest(BaseModel):
    """ログイン識別子で申し込む。

    メールアドレスは任意項目なので、それを起点にはできない（ADR-0011）。
    """

    username: str = Field(min_length=1, max_length=USERNAME_MAX_LENGTH)


class ResetPasswordRequest(BaseModel):
    token: str
    new_password: str = Field(min_length=8)


class StatusResponse(BaseModel):
    status: str


__all__ = [
    "DISPLAY_NAME_MAX_LENGTH",
    "ChangePasswordRequest",
    "ForgotPasswordRequest",
    "LoginRequest",
    "MeResponse",
    "ProfileUpdateRequest",
    "RefreshRequest",
    "ResetPasswordRequest",
    "StatusResponse",
    "TokenResponse",
]
