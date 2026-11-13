"""Display device pairing (ADR-0047; modeled on RFC 8628).

1. The device starts (:class:`StartPairingUseCase`) — receives a confirmation code and a device secret
2. An operator approves with the confirmation code (:class:`ApprovePairingUseCase`) — a display account is created
3. The device claims with its secret (:class:`ClaimPairingUseCase`) — receives the device credential exactly once

reward_points creates the display account (as a family membership). Approval takes
that as ``enroll`` and calls it only once the confirmation code is known to be usable.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

from bounded_contexts.display_devices.domain.entities.display_pairing import DisplayPairing
from bounded_contexts.display_devices.domain.exceptions import (
    AuthorizationPendingError,
    ExpiredTokenError,
    PairingExpiredError,
    PairingNotFoundError,
)
from bounded_contexts.display_devices.domain.repositories.display_credential_repository import (
    IDisplayCredentialRepository,
)
from bounded_contexts.display_devices.domain.repositories.display_pairing_repository import (
    IDisplayPairingRepository,
)
from bounded_contexts.display_devices.domain.services import pairing_secrets
from bounded_contexts.display_devices.domain.services.pairing_rules import (
    PAIRING_RETENTION,
    PAIRING_TTL,
    POLL_INTERVAL_SECONDS,
)
from shared.kernel.timestamps import utcnow

# Retries when a confirmation code collides with a live row. 31 symbols x 8 chars, so it practically never happens
_USER_CODE_ATTEMPTS = 5


@dataclass(frozen=True, kw_only=True)
class StartedPairing:
    """What is returned to the device. The plaintext is available this one time only."""

    #: Confirmation code shown on screen (``KQ7M-3XPA``)
    user_code: str
    #: Secret known only to the device; required to claim
    device_code: str
    expires_in: int
    interval: int


class StartPairingUseCase:
    def __init__(self, pairings: IDisplayPairingRepository) -> None:
        self._pairings = pairings

    def execute(self) -> StartedPairing:
        now = utcnow()
        # Anyone can call this endpoint, so clean up old rows here to keep them from piling up
        self._pairings.delete_expired_before(now - PAIRING_RETENTION)
        user_code = self._fresh_user_code()
        device_code = pairing_secrets.new_secret()
        self._pairings.add(
            user_code_hash=pairing_secrets.hash_secret(user_code),
            device_code_hash=pairing_secrets.hash_secret(device_code),
            expires_at=now + PAIRING_TTL,
        )
        return StartedPairing(
            user_code=pairing_secrets.format_user_code(user_code),
            device_code=device_code,
            expires_in=int(PAIRING_TTL.total_seconds()),
            interval=POLL_INTERVAL_SECONDS,
        )

    def _fresh_user_code(self) -> str:
        for _ in range(_USER_CODE_ATTEMPTS):
            code = pairing_secrets.new_user_code()
            if not self._pairings.is_user_code_in_use(pairing_secrets.hash_secret(code)):
                return code
        raise RuntimeError("could not find a free pairing code")


class ApprovePairingUseCase:
    def __init__(self, pairings: IDisplayPairingRepository) -> None:
        self._pairings = pairings

    def execute(self, *, user_code: str, enroll: Callable[[], int]) -> int:
        """Approve the confirmation code and link the display account created by ``enroll``.

        ``enroll`` is called once, only after the code is known to be usable, so a
        typo never creates a display account. Returns the linked account's ID.
        """
        pairing = self._approvable(user_code)
        account_id = enroll()
        self._pairings.mark_approved(pairing_id=pairing.id, account_id=account_id, approved_at=utcnow())
        return account_id

    def _approvable(self, user_code: str) -> DisplayPairing:
        normalized = pairing_secrets.normalize_user_code(user_code)
        if normalized is None:
            raise PairingNotFoundError
        pairing = self._pairings.find_by_user_code(pairing_secrets.hash_secret(normalized))
        if pairing is None or pairing.is_approved or pairing.is_claimed:
            raise PairingNotFoundError
        if not pairing.can_be_approved(utcnow()):
            raise PairingExpiredError
        return pairing


class ClaimPairingUseCase:
    def __init__(self, pairings: IDisplayPairingRepository, credentials: IDisplayCredentialRepository) -> None:
        self._pairings = pairings
        self._credentials = credentials

    def execute(self, device_code: str) -> str:
        """If approved, return the device credential (plaintext) exactly once."""
        now = utcnow()
        pairing = self._pairings.find_by_device_code(pairing_secrets.hash_secret(device_code))
        if pairing is None or pairing.is_claimed or pairing.is_expired(now):
            raise ExpiredTokenError
        if pairing.approved_account_id is None:
            raise AuthorizationPendingError
        credential = pairing_secrets.new_secret()
        self._credentials.replace(
            account_id=pairing.approved_account_id,
            credential_hash=pairing_secrets.hash_secret(credential),
            issued_at=now,
        )
        self._pairings.mark_claimed(pairing_id=pairing.id, claimed_at=now)
        return credential


__all__ = [
    "ApprovePairingUseCase",
    "ClaimPairingUseCase",
    "StartPairingUseCase",
    "StartedPairing",
]
