"""ペアリングの置き場。確認コードと端末の秘密はハッシュで渡す（平文は置かない）。"""

from __future__ import annotations

from abc import ABC, abstractmethod
from datetime import datetime

from bounded_contexts.display_devices.domain.entities.display_pairing import DisplayPairing


class IDisplayPairingRepository(ABC):
    @abstractmethod
    def add(self, *, user_code_hash: str, device_code_hash: str, expires_at: datetime) -> DisplayPairing: ...

    @abstractmethod
    def is_user_code_in_use(self, user_code_hash: str) -> bool:
        """同じ確認コードの行が残っているか（作るときの衝突よけ）。"""

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
        """*moment* より前に期限が切れた行を消す（溜めない）。"""


__all__ = ["IDisplayPairingRepository"]
