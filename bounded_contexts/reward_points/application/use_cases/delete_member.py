"""メンバーを削除する（履歴・共有ごと。所有者のみ）。

``MANAGE`` で共有された相手にまで削除を許すと、所有者のメンバーと履歴すべてを
共有先が消せてしまう。記録する権限と、消してしまう権限は分ける（ADR-0007）。
"""

from __future__ import annotations

from bounded_contexts.reward_points.application.member_access_resolver import MemberAccessResolver
from bounded_contexts.reward_points.domain.repositories.member_repository import IMemberRepository


class DeleteMemberUseCase:
    def __init__(self, access: MemberAccessResolver, members: IMemberRepository) -> None:
        self._access = access
        self._members = members

    def execute(self, *, member_id: int, user_id: int) -> None:
        self._access.require_ownership(member_id=member_id, user_id=user_id)
        self._members.delete(member_id)


__all__ = ["DeleteMemberUseCase"]
