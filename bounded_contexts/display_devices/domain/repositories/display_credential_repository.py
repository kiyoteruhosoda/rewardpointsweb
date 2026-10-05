"""端末の資格情報の置き場。1 表示アカウントに 1 つ（1 端末 = 1 アカウント。ADR-0047）。"""

from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import Set
from dataclasses import dataclass
from datetime import datetime


@dataclass(frozen=True, kw_only=True)
class DisplayCredential:
    account_id: int
    created_at: datetime
    last_used_at: datetime


class IDisplayCredentialRepository(ABC):
    @abstractmethod
    def replace(self, *, account_id: int, credential_hash: str, issued_at: datetime) -> None:
        """*account_id* の資格情報を（あれば差し替えて）置く。"""

    @abstractmethod
    def find_by_hash(self, credential_hash: str) -> DisplayCredential | None: ...

    @abstractmethod
    def touch(self, *, account_id: int, used_at: datetime) -> None:
        """最後に使った日時を書く。"""

    @abstractmethod
    def delete(self, account_id: int) -> None: ...

    @abstractmethod
    def account_ids(self) -> Set[int]:
        """資格情報を持つ表示アカウント（入れる手段の棚卸し。ADR-0035）。"""

    @abstractmethod
    def last_used(self) -> dict[int, datetime]:
        """表示アカウント -> 最後に使った日時（運用管理者の一覧に出す）。"""


__all__ = ["DisplayCredential", "IDisplayCredentialRepository"]
