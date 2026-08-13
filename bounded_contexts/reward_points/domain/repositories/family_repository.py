"""家族の永続化インターフェース。"""

from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import Sequence

from bounded_contexts.reward_points.domain.entities.family import Family


class IFamilyRepository(ABC):
    @abstractmethod
    def add(self, *, name: str, rules: str | None = None) -> Family:
        """家族を作る。``rules`` は控えからの復元でだけ渡す（ADR-0026）。"""

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

    @abstractmethod
    def update_name(self, *, family_id: int, name: str) -> Family:
        """家族名を変える（改名は owner だけができる。ADR-0013）。"""

    @abstractmethod
    def update_rules(self, *, family_id: int, rules: str | None) -> Family:
        """家族のルールを書き換える（``None`` で消す。ADR-0027）。"""

    @abstractmethod
    def delete(self, family_id: int) -> None:
        """家族を消す（解散）。参加・招待は家族と一緒に消える。"""


__all__ = ["IFamilyRepository"]
