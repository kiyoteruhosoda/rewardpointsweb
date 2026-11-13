"""Pydantic schemas for authentication.

The login identifier is ``username``. Email address is optional, so it cannot be
used as an identifier (ADR-0011).
"""

from __future__ import annotations

from pydantic import BaseModel, EmailStr, Field, field_validator

from shared.domain.auth.password_policy import MAX_LENGTH as PASSWORD_MAX_LENGTH
from shared.domain.auth.password_policy import MIN_LENGTH as PASSWORD_MIN_LENGTH
from shared.domain.auth.username import MAX_LENGTH as USERNAME_MAX_LENGTH

DISPLAY_NAME_MAX_LENGTH = 100


class LoginRequest(BaseModel):
    username: str = Field(min_length=1, max_length=USERNAME_MAX_LENGTH)
    password: str = Field(max_length=PASSWORD_MAX_LENGTH)
    # Required only for accounts with two-factor auth enabled (returns totp_required if missing)
    totp_code: str | None = None


class TokenResponse(BaseModel):
    access_token: str
    #: Not issued for SSO logins (``None``. ADR-0058)
    refresh_token: str | None = None
    token_type: str
    expires_in: int
    # Login with a temporary password. The UI leads the user to change the password (ADR-0011)
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
    # Whether the user has a password entrance (ADR-0034). ⚠ **When false, the UI does not
    # offer password change**: otherwise a user who cannot enter a "current password"
    # would be shown a form that can never succeed.
    has_password: bool = True
    # Whether this is a display device (signage) session (ADR-0047). If true, the UI shows only the display screen (/display)
    display_device: bool = False


class ProfileUpdateRequest(BaseModel):
    """Change of display name and email address.

    Sending ``null`` for ``email`` removes the email address. Omitting it leaves it
    unchanged ("sent ``null``" and "did not send" are told apart via
    ``model_fields_set``).
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
    current_password: str = Field(max_length=PASSWORD_MAX_LENGTH)
    new_password: str = Field(min_length=PASSWORD_MIN_LENGTH, max_length=PASSWORD_MAX_LENGTH)


class ForgotPasswordRequest(BaseModel):
    """Request by login identifier.

    Email address is optional, so it cannot be the starting point (ADR-0011).
    """

    username: str = Field(min_length=1, max_length=USERNAME_MAX_LENGTH)


class ResetPasswordRequest(BaseModel):
    token: str
    new_password: str = Field(min_length=PASSWORD_MIN_LENGTH, max_length=PASSWORD_MAX_LENGTH)


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
