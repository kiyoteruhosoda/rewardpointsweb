"""メンバーの永続化インターフェース。"""

from __future__ import annotations

from abc import ABC, abstractmethod

from bounded_contexts.reward_points.domain.entities.member import Member


class IMemberRepository(ABC):
    @abstractmethod
    def add(self, *, name: str, owner_user_id: int, linked_user_id: int | None) -> Member: ...

    @abstractmethod
    def find_by_id(self, member_id: int) -> Member | None: ...

    @abstractmethod
    def find_by_linked_user(self, user_id: int) -> Member | None: ...

    @abstractmethod
    def find_reachable_by(self, user_id: int) -> list[Member]:
        """*user_id* が何らかの経路（所有・共有・本人）で到達できるメンバー。

        「どこまで触れるか」は返さない。範囲の判定は
        :class:`~bounded_contexts.reward_points.domain.services.member_access_policy.MemberAccessPolicy`
        の責務で、ここは候補を絞り込むだけ。
        """

    @abstractmethod
    def delete(self, member_id: int) -> None:
        """メンバーと、それに属する履歴・共有をまとめて消す。"""


__all__ = ["IMemberRepository"]
