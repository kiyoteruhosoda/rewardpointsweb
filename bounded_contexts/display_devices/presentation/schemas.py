"""Requests and responses for the display devices API (ADR-0047)."""

from __future__ import annotations

from pydantic import BaseModel, Field

from presentation.fastapi.schemas.types import UtcDatetime


class PairingStartRequest(BaseModel):
    #: Origin the device has open (``https://…``). Used as the target of the QR code pointing to the approval screen.
    #: If omitted, no QR code is returned (approval still works by typing the confirmation code)
    origin: str | None = Field(default=None, max_length=200, pattern=r"^https?://[^/\s#?]+$")


class PairingStartResponse(BaseModel):
    #: Confirmation code shown on screen (``KQ7M-3XPA``). The operator types it on the approval screen
    user_code: str
    #: Secret known only to the device. Needed to claim the credential. Never shown on screen
    device_code: str
    expires_in: int
    #: Interval for polling the claim endpoint (seconds)
    interval: int
    #: QR code pointing to the approval screen (with the confirmation code), as an SVG data URI.
    #: ``None`` if ``origin`` was not sent
    qr_code: str | None = None


class PairingClaimRequest(BaseModel):
    device_code: str = Field(min_length=1, max_length=128)


class PairingClaimResponse(BaseModel):
    #: Device credential. Exchanged for an access token via ``POST /api/display/session``
    device_credential: str


class PairingApproveRequest(BaseModel):
    user_code: str = Field(min_length=1, max_length=32)
    family_id: int
    #: Device name (e.g. "Living room"). Also listed under this name among the family members
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
    #: When an access token was last obtained. ``None`` before the credential is claimed
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
