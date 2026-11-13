"""Domain exceptions of the account security context.

The presentation layer converts these into HTTP status + error code
(conversion to display text is done by the frontend; see CLAUDE.md "Internationalization").
"""

from __future__ import annotations


class AccountSecurityError(Exception):
    """Base exception of this context. ``code`` becomes the API error code as is."""

    code = "account_security_error"


class TotpAlreadyEnabledError(AccountSecurityError):
    """Tried to start enrollment on an account that already has two-factor authentication enabled."""

    code = "totp_already_enabled"


class TotpNotEnrolledError(AccountSecurityError):
    """Enrollment has not started (nothing to verify the confirmation code against)."""

    code = "totp_not_enrolled"


class InvalidTotpCodeError(AccountSecurityError):
    """The confirmation code does not match."""

    code = "invalid_totp"


class TotpRequiredError(AccountSecurityError):
    """Two-factor authentication is enabled but no code was presented."""

    code = "totp_required"


class ChallengeNotFoundError(AccountSecurityError):
    """WebAuthn challenge not found (expired, already used, or in another process)."""

    code = "challenge_not_found"


class PasskeyVerificationError(AccountSecurityError):
    """WebAuthn signature verification failed."""

    code = "passkey_verification_failed"


class PasskeyAlreadyRegisteredError(AccountSecurityError):
    """The same credential is already registered to another account."""

    code = "passkey_already_registered"


class PasskeyNotFoundError(AccountSecurityError):
    """The specified passkey does not exist (including ones owned by someone else)."""

    code = "passkey_not_found"


class PasskeyConfigurationError(AccountSecurityError):
    """The passkey settings (RP ID, origin) do not follow WebAuthn rules.

    A configuration mistake, not a user action. Stop issuing passkeys and have an administrator fix it.
    """

    code = "passkey_misconfigured"


class InvalidWebAuthnOriginError(PasskeyConfigurationError):
    """``WEBAUTHN_ORIGIN`` cannot be used as a URL (wrong scheme or host)."""

    code = "invalid_webauthn_origin"


class InvalidWebAuthnRelyingPartyIdError(PasskeyConfigurationError):
    """``WEBAUTHN_RP_ID`` does not match the origin's domain."""

    code = "invalid_webauthn_rp_id"


class TooManyAttemptsError(AccountSecurityError):
    """Rejected for a while after too many failures in a short time (ADR-0055).

    Do not hide this in ``401``. If the user cannot tell they are being refused, they keep getting
    rejected even with the right password, assume they "forgot" it, and head to a reset.
    """

    code = "too_many_attempts"

    def __init__(self, retry_after_seconds: int) -> None:
        super().__init__(f"retry after {retry_after_seconds}s")
        self.retry_after_seconds = retry_after_seconds


__all__ = [
    "AccountSecurityError",
    "ChallengeNotFoundError",
    "InvalidTotpCodeError",
    "InvalidWebAuthnOriginError",
    "InvalidWebAuthnRelyingPartyIdError",
    "PasskeyAlreadyRegisteredError",
    "PasskeyConfigurationError",
    "PasskeyNotFoundError",
    "PasskeyVerificationError",
    "TooManyAttemptsError",
    "TotpAlreadyEnabledError",
    "TotpNotEnrolledError",
    "TotpRequiredError",
]
