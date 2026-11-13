"""Decide, from a device credential, which display account to sign in as (ADR-0047).

⚠ **This entry point hits the DB every time** (ADR-0037 decisions 3 and 4: "paths
that reissue do the lookup"). A removed device's credential row is deleted, so its
next refresh is refused.
"""

from __future__ import annotations

from collections.abc import Set
from datetime import datetime

from bounded_contexts.display_devices.domain.exceptions import (
    DeviceCredentialExpiredError,
    InvalidDeviceCredentialError,
)
from bounded_contexts.display_devices.domain.repositories.display_credential_repository import (
    IDisplayCredentialRepository,
)
from bounded_contexts.display_devices.domain.services import pairing_secrets
from bounded_contexts.display_devices.domain.services.pairing_rules import CREDENTIAL_IDLE_LIMIT
from shared.kernel.timestamps import utcnow


class OpenDisplaySessionUseCase:
    def __init__(self, credentials: IDisplayCredentialRepository) -> None:
        self._credentials = credentials

    def execute(self, device_credential: str) -> int:
        """Return the display account ID and record the last-used time.

        If the credential has been unused for longer than :data:`CREDENTIAL_IDLE_LIMIT`,
        delete it and raise :class:`DeviceCredentialExpiredError` (the caller removes
        the device).
        """
        now = utcnow()
        found = self._credentials.find_by_hash(pairing_secrets.hash_secret(device_credential))
        if found is None:
            raise InvalidDeviceCredentialError
        if found.last_used_at + CREDENTIAL_IDLE_LIMIT < now:
            self._credentials.delete(found.account_id)
            raise DeviceCredentialExpiredError(found.account_id)
        self._credentials.touch(account_id=found.account_id, used_at=now)
        return found.account_id


class DescribeDisplayCredentialsUseCase:
    """Inventory of credentials (how one can sign in, and when each was last used)."""

    def __init__(self, credentials: IDisplayCredentialRepository) -> None:
        self._credentials = credentials

    def holders(self) -> Set[int]:
        return self._credentials.account_ids()

    def last_used(self) -> dict[int, datetime]:
        return self._credentials.last_used()


__all__ = ["DescribeDisplayCredentialsUseCase", "OpenDisplaySessionUseCase"]
