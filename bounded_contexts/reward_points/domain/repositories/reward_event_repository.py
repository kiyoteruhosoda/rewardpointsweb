"""イベントの永続化インターフェース（ADR-0042）。

台帳が消えればイベントも消える（家族の解散・参加者の削除・独立の成立）。
達成で足した台帳の行はイベントとは別に残る — イベントを消しても台帳は動かない。
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import datetime

from bounded_contexts.reward_points.domain.entities.reward_event import RewardEvent


@dataclass(frozen=True, kw_only=True)
class NewRewardEvent:
    """これから作るイベント。"""

    ledger_id: int
    title: str
    reward: int
    goal_count: int


class IRewardEventRepository(ABC):
    @abstractmethod
    def list_by_ledger(self, ledger_id: int) -> list[RewardEvent]:
        """作った順（古いものが先）。"""

    @abstractmethod
    def find_in_ledger(self, *, ledger_id: int, event_id: int) -> RewardEvent | None:
        """他の台帳のイベントを指したときは ``None``。"""

    @abstractmethod
    def add(self, new_event: NewRewardEvent) -> RewardEvent: ...

    @abstractmethod
    def stick(self, *, event_id: int, number: int, stuck_at: datetime, stuck_by_membership_id: int) -> bool:
        """*number* 枚目を貼る。

        同じ番号が同時に貼られていた（``UNIQUE (event_id, number)`` に当たった）
        ときは偽を返す。貼ったのは向こうなので、達成の後始末も向こうが行う。
        """

    @abstractmethod
    def peel(self, *, event_id: int, number: int) -> None:
        """*number* 枚目をはがす。無ければ何もしない。"""

    @abstractmethod
    def mark_completed(self, *, event_id: int, completed_at: datetime, awarded_transaction_id: int) -> None:
        """マスが埋まり、台帳へ *awarded_transaction_id* を足したことを記録する。"""

    @abstractmethod
    def delete(self, event_id: int) -> None:
        """イベントを消す。台帳の履歴には触れない。"""


__all__ = ["IRewardEventRepository", "NewRewardEvent"]
