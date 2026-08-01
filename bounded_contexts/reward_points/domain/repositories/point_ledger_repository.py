"""ポイント台帳の永続化インターフェース。"""

from __future__ import annotations

from abc import ABC, abstractmethod

from bounded_contexts.reward_points.domain.entities.point_ledger import PointLedger


class IPointLedgerRepository(ABC):
    @abstractmethod
    def add(self, *, family_id: int, membership_id: int) -> PointLedger: ...

    @abstractmethod
    def find_by_id(self, ledger_id: int) -> PointLedger | None: ...

    @abstractmethod
    def find_by_membership(self, membership_id: int) -> PointLedger | None: ...

    @abstractmethod
    def list_for_family(self, family_id: int) -> list[PointLedger]: ...

    @abstractmethod
    def delete(self, ledger_id: int) -> None: ...


__all__ = ["IPointLedgerRepository"]
