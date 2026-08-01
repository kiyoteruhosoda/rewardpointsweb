"""アカウントを削除してよいか確かめる。

ユーザー管理（``/api/admin/users``）から呼ぶ。owner が消えるとその家族を
管理できる人がいなくなるので、一緒に消すのではなく削除自体を断る。
"""

from __future__ import annotations

from bounded_contexts.reward_points.domain.exceptions import UserStillOwnsFamiliesError
from bounded_contexts.reward_points.domain.repositories.family_repository import IFamilyRepository


class EnsureUserCanBeDeletedUseCase:
    def __init__(self, families: IFamilyRepository) -> None:
        self._families = families

    def execute(self, *, user_id: int) -> None:
        if self._families.count_owned_by(user_id) > 0:
            raise UserStillOwnsFamiliesError


__all__ = ["EnsureUserCanBeDeletedUseCase"]
