"""Pydantic schemas for the admin API."""

from __future__ import annotations

from pydantic import BaseModel, EmailStr, Field

from shared.domain.auth.username import MAX_LENGTH as USERNAME_MAX_LENGTH


class SignInEntrances(BaseModel):
    """List of **ways this user can sign in to this app** (ADR-0035).

    ⚠ **This is an inventory that assumes there are two auth systems.** Requiring MFA on
    the IdP does not apply to this app's passwords and passkeys. How many entrances are
    open only becomes clear when they are listed side by side.
    """

    #: Whether the user can sign in with a password (``users.password_hash`` is not NULL. ADR-0034).
    password: bool = False
    #: Whether this app's two-factor auth (TOTP) is enabled. **Separate from MFA on the IdP.**
    totp: bool = False
    #: Number of passkeys registered in this app. **Separate from passkeys on the IdP.**
    passkeys: int = 0
    #: Issuers of linked IdPs. Empty = cannot sign in via SSO.
    identity_providers: list[str] = []
    #: Whether the user can sign in as a paired display device (ADR-0047). Only this is true for display accounts.
    display_device: bool = False


class UserResponse(BaseModel):
    id: int
    # Login identifier. Email address is optional (ADR-0011)
    username: str
    email: str | None
    display_name: str
    is_active: bool
    must_change_password: bool
    roles: list[str]
    # Scopes actually in effect (union of the permissions of the user's roles). What a person
    # can do after their roles change cannot be read from role names alone.
    permissions: list[str]
    #: List of sign-in entrances (ADR-0035). Returned in the same shape by list, create and update.
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
    # Only for items with choices. A list of [value, display label].
    choices: list[list[str]] | None = None
    # Services that need a restart to apply (empty = applied on save)
    restart_scopes: list[str] = []
    # Setting decided only by environment variables (read-only. ADR-0056)
    env_only: bool = False
    value: object = None
    default: object = None
    env_fallback: bool
    stored: bool


class SystemSettingsUpdateRequest(BaseModel):
    # key -> new value (null deletes the DB override for that key and reverts to the default)
    values: dict[str, object]


class RestartRequirementResponse(BaseModel):
    """Saved settings that need a restart to take effect."""

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
    # If omitted, all services are targeted
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
