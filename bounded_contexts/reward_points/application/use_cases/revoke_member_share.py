"""共有を取り消す（要 ``MANAGE``）。"""

from __future__ import annotations

from bounded_contexts.reward_points.application.member_access_resolver import MemberAccessResolver
from bounded_contexts.reward_points.domain.exceptions import MemberShareNotFoundError
from bounded_contexts.reward_points.domain.repositories.member_share_repository import IMemberShareRepository


class RevokeMemberShareUseCase:
    def __init__(self, access: MemberAccessResolver, shares: IMemberShareRepository) -> None:
        self._access = access
        self._shares = shares

    def execute(self, *, member_id: int, target_user_id: int, user_id: int) -> None:
        self._access.require_manage(member_id=member_id, user_id=user_id)
        if not self._shares.revoke(member_id=member_id, user_id=target_user_id):
            raise MemberShareNotFoundError


__all__ = ["RevokeMemberShareUseCase"]
