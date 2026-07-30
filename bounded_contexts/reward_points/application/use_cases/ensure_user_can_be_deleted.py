"""アカウントを削除してよいか確かめる。

ユーザー管理（`/api/admin/users`）から呼ぶ。`members.owner_user_id` は外部キーで
`users.id` を参照するため、メンバーを残したままアカウントを消すと DB が拒み、
API は 500 を返してしまう。所有者が消えたメンバーは誰も管理できないので、
一緒に消すのではなく削除自体を断る（ADR-0007）。
"""

from __future__ import annotations

from bounded_contexts.reward_points.domain.exceptions import UserStillOwnsMembersError
from bounded_contexts.reward_points.domain.repositories.member_repository import IMemberRepository


class EnsureUserCanBeDeletedUseCase:
    def __init__(self, members: IMemberRepository) -> None:
        self._members = members

    def execute(self, *, user_id: int) -> None:
        if self._members.count_owned_by(user_id) > 0:
            raise UserStillOwnsMembersError


__all__ = ["EnsureUserCanBeDeletedUseCase"]
