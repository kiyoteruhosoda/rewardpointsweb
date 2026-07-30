"""メンバーの共有（誰に、どこまで渡したか）。

同一メンバー・同一ユーザーの組で 1 件（``member_id`` + ``user_id`` が識別子）。
"""

from __future__ import annotations

from dataclasses import dataclass

from bounded_contexts.reward_points.domain.value_objects.member_access_level import MemberAccessLevel


@dataclass(frozen=True, kw_only=True)
class MemberShare:
    member_id: int
    user_id: int
    level: MemberAccessLevel

    def grants_to(self, user_id: int, member_id: int) -> bool:
        return self.user_id == user_id and self.member_id == member_id


__all__ = ["MemberShare"]
