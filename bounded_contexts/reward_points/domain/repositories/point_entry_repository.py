"""ポイント履歴の永続化インターフェース。"""

from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import Mapping, Sequence
from datetime import datetime

from bounded_contexts.reward_points.domain.entities.point_entry import PointEntry


class IPointEntryRepository(ABC):
    @abstractmethod
    def list_by_member(self, member_id: int) -> list[PointEntry]:
        """発生日時の新しい順。"""

    @abstractmethod
    def list_by_members(self, member_ids: Sequence[int]) -> Mapping[int, list[PointEntry]]:
        """メンバー ID -> 履歴。一覧の残高計算で 1 件ずつ引かないための入口。"""

    @abstractmethod
    def add_addition(
        self,
        *,
        member_id: int,
        occurred_at: datetime,
        points: int,
        reason: str,
        recorded_by_user_id: int,
    ) -> PointEntry: ...

    @abstractmethod
    def add_consumption(
        self,
        *,
        member_id: int,
        occurred_at: datetime,
        points: int,
        application: str,
        recorded_by_user_id: int,
    ) -> PointEntry: ...

    @abstractmethod
    def delete(self, *, member_id: int, entry_id: int) -> bool:
        """履歴を消す。そのメンバーの履歴でなければ ``False``（他人の履歴は消せない）。"""


__all__ = ["IPointEntryRepository"]
