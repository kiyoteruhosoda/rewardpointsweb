"""管理 API の Pydantic スキーマ。"""

from __future__ import annotations

from pydantic import BaseModel, EmailStr, Field

from shared.domain.auth.username import MAX_LENGTH as USERNAME_MAX_LENGTH


class SignInEntrances(BaseModel):
    """この利用者が**このアプリへ入れる手段**の一覧（ADR-0035）。

    ⚠ **認証系が 2 つあることを前提にした棚卸しのための値である。** IdP 側で
    多要素を必須にしても、こちらのパスワード・パスキーには掛からない。何本の口が
    開いているのかは、並べて見ないと分からない。
    """

    #: パスワードで入れるか（``users.password_hash`` が NULL でない。ADR-0034）。
    password: bool = False
    #: このアプリ側の二要素認証（TOTP）が有効か。**IdP 側の多要素とは別物。**
    totp: bool = False
    #: このアプリ側に登録されたパスキーの本数。**IdP 側のパスキーとは別物。**
    passkeys: int = 0
    #: 結び付いている IdP の issuer。空 = SSO では入れない。
    identity_providers: list[str] = []


class UserResponse(BaseModel):
    id: int
    # ログイン識別子。メールアドレスは任意項目（ADR-0011）
    username: str
    email: str | None
    display_name: str
    is_active: bool
    must_change_password: bool
    roles: list[str]
    # 実際に効いている scope（所属ロールの権限の和集合）。ロールを付け替えた
    # 結果その人が何を行えるようになったかは、ロール名だけでは読み取れない。
    permissions: list[str]
    #: 入れる手段の一覧（ADR-0035）。一覧・作成・更新のどれでも同じ形で返す。
    entrances: SignInEntrances = SignInEntrances()


class UserCreateRequest(BaseModel):
    username: str = Field(min_length=1, max_length=USERNAME_MAX_LENGTH)
    email: EmailStr | None = None
    display_name: str = Field(min_length=1, max_length=100)
    password: str = Field(min_length=8)
    roles: list[str] = []


class UserUpdateRequest(BaseModel):
    display_name: str | None = Field(default=None, min_length=1, max_length=100)
    is_active: bool | None = None
    roles: list[str] | None = None
    password: str | None = Field(default=None, min_length=8)


class RoleResponse(BaseModel):
    id: int
    name: str
    permissions: list[str]


class RoleCreateRequest(BaseModel):
    name: str = Field(min_length=1, max_length=50)
    permissions: list[str] = []


class RoleUpdateRequest(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=50)
    permissions: list[str] | None = None


class PermissionResponse(BaseModel):
    id: int
    code: str


class SystemSettingItemResponse(BaseModel):
    key: str
    category: str
    label: str
    value_type: str
    secret: bool = False
    # 選択肢を持つ項目のみ。[値, 表示ラベル] の並び。
    choices: list[list[str]] | None = None
    # 反映に再起動が必要なサービス（空 = 保存と同時に反映）
    restart_scopes: list[str] = []
    value: object = None
    default: object = None
    env_fallback: bool
    stored: bool


class SystemSettingsUpdateRequest(BaseModel):
    # key -> 新しい値（null でその key の DB 上書きを削除しデフォルトへ戻す）
    values: dict[str, object]


class RestartRequirementResponse(BaseModel):
    """保存した設定のうち、反映に再起動が必要なもの。"""

    scopes: list[str] = []
    keys: list[str] = []


class SystemSettingsUpdateResponse(BaseModel):
    status: str
    restart_required: RestartRequirementResponse | None = None


class RestartRequestResponse(BaseModel):
    scope: str
    token: str
    requested_at: str | None = None
    requested_by: str | None = None
    reason: str | None = None


class RestartStatusResponse(BaseModel):
    available_scopes: list[str]
    last_requests: list[RestartRequestResponse]


class RestartCommandRequest(BaseModel):
    # 省略時は全サービスが対象
    scopes: list[str] | None = None
    reason: str | None = None


class RestartCommandResponse(BaseModel):
    requested: bool
    requests: list[RestartRequestResponse]


class LogEntryResponse(BaseModel):
    id: int
    created_at: str
    level: str
    logger: str
    message: str
    request_id: str | None
    user_id_hash: str | None
    path: str | None
    method: str | None
    status_code: int | None
    duration_ms: int | None
    trace: str | None
