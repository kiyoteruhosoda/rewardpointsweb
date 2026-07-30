"""ポイント履歴 1 件。

加算（:class:`PointAddition`）と消費（:class:`PointConsumption`）の 2 種類があり、
残高への効き方（符号）と説明の呼び名（理由 / 用途）だけが違う。呼び出し側で
``if entry_type == ...`` と分岐せずに済むよう、その違いは各サブクラスの
``signed_points`` / ``description`` に閉じ込める。
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import datetime

from bounded_contexts.reward_points.domain.value_objects.entry_description import EntryDescription
from bounded_contexts.reward_points.domain.value_objects.point_amount import PointAmount
from bounded_contexts.reward_points.domain.value_objects.point_entry_type import PointEntryType


@dataclass(frozen=True, kw_only=True)
class PointEntry(ABC):
    id: int
    member_id: int
    occurred_at: datetime
    amount: PointAmount
    recorded_by_user_id: int

    @property
    @abstractmethod
    def entry_type(self) -> PointEntryType:
        """種別（永続化・表示のための識別子）。"""

    @property
    @abstractmethod
    def signed_points(self) -> int:
        """残高へ足し込む値。加算は正、消費は負。"""

    @property
    @abstractmethod
    def description(self) -> EntryDescription:
        """加算なら理由、消費なら用途。履歴を 1 列に並べるための共通の呼び名。"""


@dataclass(frozen=True, kw_only=True)
class PointAddition(PointEntry):
    reason: EntryDescription

    @property
    def entry_type(self) -> PointEntryType:
        return PointEntryType.ADDITION

    @property
    def signed_points(self) -> int:
        return self.amount.value

    @property
    def description(self) -> EntryDescription:
        return self.reason


@dataclass(frozen=True, kw_only=True)
class PointConsumption(PointEntry):
    application: EntryDescription

    @property
    def entry_type(self) -> PointEntryType:
        return PointEntryType.CONSUMPTION

    @property
    def signed_points(self) -> int:
        return -self.amount.value

    @property
    def description(self) -> EntryDescription:
        return self.application


__all__ = ["PointAddition", "PointConsumption", "PointEntry"]
