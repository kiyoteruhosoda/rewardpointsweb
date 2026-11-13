"""Storage for device credentials. One per display account (1 device = 1 account, ADR-0047)."""

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
        """Store the credential for *account_id* (replacing any existing one)."""

    @abstractmethod
    def find_by_hash(self, credential_hash: str) -> DisplayCredential | None: ...

    @abstractmethod
    def touch(self, *, account_id: int, used_at: datetime) -> None:
        """Record the last-used time."""

    @abstractmethod
    def delete(self, account_id: int) -> None: ...

    @abstractmethod
    def account_ids(self) -> Set[int]:
        """Display accounts that hold a credential (inventory of sign-in means, ADR-0035)."""

    @abstractmethod
    def last_used(self) -> dict[int, datetime]:
        """Display account -> last-used time (shown in the operator's list)."""


__all__ = ["DisplayCredential", "IDisplayCredentialRepository"]
