"""メンバーを削除する（履歴・共有ごと）。"""

from __future__ import annotations

from bounded_contexts.reward_points.application.member_access_resolver import MemberAccessResolver
from bounded_contexts.reward_points.domain.repositories.member_repository import IMemberRepository


class DeleteMemberUseCase:
    def __init__(self, access: MemberAccessResolver, members: IMemberRepository) -> None:
        self._access = access
        self._members = members

    def execute(self, *, member_id: int, user_id: int) -> None:
        self._access.require_manage(member_id=member_id, user_id=user_id)
        self._members.delete(member_id)


__all__ = ["DeleteMemberUseCase"]
