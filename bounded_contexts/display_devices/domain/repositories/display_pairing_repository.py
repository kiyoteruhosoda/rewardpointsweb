"""Storage for pairings. The confirmation code and device secret are passed as hashes (no plaintext is stored)."""

from __future__ import annotations

from abc import ABC, abstractmethod
from datetime import datetime

from bounded_contexts.display_devices.domain.entities.display_pairing import DisplayPairing


class IDisplayPairingRepository(ABC):
    @abstractmethod
    def add(self, *, user_code_hash: str, device_code_hash: str, expires_at: datetime) -> DisplayPairing: ...

    @abstractmethod
    def is_user_code_in_use(self, user_code_hash: str) -> bool:
        """Whether a row with the same confirmation code still exists (to avoid collisions on create)."""

    @abstractmethod
    def find_by_user_code(self, user_code_hash: str) -> DisplayPairing | None: ...

    @abstractmethod
    def find_by_device_code(self, device_code_hash: str) -> DisplayPairing | None: ...

    @abstractmethod
    def mark_approved(self, *, pairing_id: int, account_id: int, approved_at: datetime) -> None: ...

    @abstractmethod
    def mark_claimed(self, *, pairing_id: int, claimed_at: datetime) -> None: ...

    @abstractmethod
    def delete_expired_before(self, moment: datetime) -> None:
        """Delete rows that expired before *moment* (so they do not pile up)."""


__all__ = ["IDisplayPairingRepository"]
