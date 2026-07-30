"""メンバーへのアクセス範囲を解決する入口。

すべてのユースケースは、対象メンバーを触る前にここを通す。判定そのものは
ドメインの :class:`MemberAccessPolicy` が持ち、ここは「読み込んで、判定させて、
足りなければ例外にする」までを受け持つ。

到達経路がまったく無い相手には **``member_not_found``** を返す（``forbidden`` だと
「そのメンバーは存在する」ことが分かってしまう）。到達はできるが変更権が無い場合
だけ ``member_access_denied`` になる。
"""

from __future__ import annotations

from bounded_contexts.reward_points.domain.exceptions import (
    MemberAccessDeniedError,
    MemberNotFoundError,
)
from bounded_contexts.reward_points.domain.repositories.member_repository import IMemberRepository
from bounded_contexts.reward_points.domain.repositories.member_share_repository import IMemberShareRepository
from bounded_contexts.reward_points.domain.services.member_access_policy import MemberAccessPolicy
from bounded_contexts.reward_points.domain.value_objects.member_access import MemberAccess


class MemberAccessResolver:
    def __init__(self, members: IMemberRepository, shares: IMemberShareRepository) -> None:
        self._members = members
        self._shares = shares

    def resolve(self, *, member_id: int, user_id: int) -> MemberAccess:
        member = self._members.find_by_id(member_id)
        if member is None:
            raise MemberNotFoundError
        level = MemberAccessPolicy.resolve(
            member,
            user_id=user_id,
            shares=self._shares.list_for_member(member_id),
        )
        if level is None:
            raise MemberNotFoundError
        return MemberAccess(member=member, level=level)

    def require_manage(self, *, member_id: int, user_id: int) -> MemberAccess:
        access = self.resolve(member_id=member_id, user_id=user_id)
        if not access.can_manage:
            raise MemberAccessDeniedError
        return access


__all__ = ["MemberAccessResolver"]
