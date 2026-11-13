"""Domain exceptions for display devices (display_devices).

``code`` is the error code the API returns as is (the frontend decides the display text).
The two used by the claim endpoint (``/api/display/pairings/claim``) follow RFC 8628 spelling.
"""

from __future__ import annotations


class DisplayDevicesError(Exception):
    code = "display_devices_error"


class PairingNotFoundError(DisplayDevicesError):
    """No pairing for that confirmation code (mistyped, or already approved)."""

    code = "pairing_not_found"


class PairingExpiredError(DisplayDevicesError):
    """The confirmation code's lifetime (10 minutes) has passed. The device has shown a new code."""

    code = "pairing_expired"


class AuthorizationPendingError(DisplayDevicesError):
    """Not approved yet. The device keeps polling at intervals (RFC 8628)."""

    code = "authorization_pending"


class ExpiredTokenError(DisplayDevicesError):
    """Expired, already claimed, or unknown device secret. The device restarts pairing (RFC 8628).

    The three are not distinguished so that a caller presenting an unknown secret is not
    told "that secret existed". The device's response is the same in every case (start over).
    """

    code = "expired_token"


class InvalidDeviceCredentialError(DisplayDevicesError):
    """Device credential missing or unknown (the device was removed). The device returns to the pairing screen."""

    code = "invalid_device_credential"


class DeviceCredentialExpiredError(DisplayDevicesError):
    """Expired after going unused (90 days). That display device is removed."""

    code = "device_credential_expired"

    def __init__(self, account_id: int) -> None:
        super().__init__(self.code)
        self.account_id = account_id


__all__ = [
    "AuthorizationPendingError",
    "DeviceCredentialExpiredError",
    "DisplayDevicesError",
    "ExpiredTokenError",
    "InvalidDeviceCredentialError",
    "PairingExpiredError",
    "PairingNotFoundError",
]
