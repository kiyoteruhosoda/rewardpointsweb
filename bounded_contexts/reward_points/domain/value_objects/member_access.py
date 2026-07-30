"""あるメンバーへの、あるユーザーのアクセス（対象と範囲の組）。"""

from __future__ import annotations

from dataclasses import dataclass

from bounded_contexts.reward_points.domain.entities.member import Member
from bounded_contexts.reward_points.domain.value_objects.member_access_level import MemberAccessLevel


@dataclass(frozen=True, kw_only=True)
class MemberAccess:
    member: Member
    level: MemberAccessLevel

    @property
    def can_manage(self) -> bool:
        return self.level.can_manage


__all__ = ["MemberAccess"]
