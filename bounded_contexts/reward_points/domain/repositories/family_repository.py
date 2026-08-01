"""家族の永続化インターフェース。"""

from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import Sequence

from bounded_contexts.reward_points.domain.entities.family import Family


class IFamilyRepository(ABC):
    @abstractmethod
    def add(self, *, name: str) -> Family: ...

    @abstractmethod
    def find_by_id(self, family_id: int) -> Family | None: ...

    @abstractmethod
    def list_by_ids(self, family_ids: Sequence[int]) -> list[Family]:
        """一覧表示のためにまとめて読む（1 件ずつ引かない）。"""

    @abstractmethod
    def count_owned_by(self, account_id: int) -> int:
        """*account_id* が owner として参加している家族の数。

        アカウントを削除してよいかの判断に使う。
        """


__all__ = ["IFamilyRepository"]
