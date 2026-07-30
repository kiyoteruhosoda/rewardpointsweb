"""メンバー共有の永続化インターフェース。"""

from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import Sequence

from bounded_contexts.reward_points.domain.entities.member_share import MemberShare
from bounded_contexts.reward_points.domain.value_objects.member_access_level import MemberAccessLevel


class IMemberShareRepository(ABC):
    @abstractmethod
    def list_for_member(self, member_id: int) -> list[MemberShare]: ...

    @abstractmethod
    def list_for_user(self, user_id: int) -> list[MemberShare]: ...

    @abstractmethod
    def list_for_members(self, member_ids: Sequence[int]) -> list[MemberShare]:
        """一覧表示のために、複数メンバーの共有をまとめて読む（1 件ずつ引かない）。"""

    @abstractmethod
    def grant(self, *, member_id: int, user_id: int, level: MemberAccessLevel) -> MemberShare: ...

    @abstractmethod
    def revoke(self, *, member_id: int, user_id: int) -> bool:
        """共有を取り消す。対象が無ければ ``False``。"""


__all__ = ["IMemberShareRepository"]
