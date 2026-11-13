"""Check whether an account may be deleted.

Called from user management (``/api/admin/users``). If the owner disappears, no one
is left to manage that family, so we refuse the deletion instead of cascading it.
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
