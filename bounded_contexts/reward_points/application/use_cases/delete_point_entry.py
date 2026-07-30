"""履歴を 1 件取り消す（要 ``MANAGE``）。

残高は履歴の合計なので、間違いは行を消して直す（打ち消しの行は作らない）。
"""

from __future__ import annotations

from bounded_contexts.reward_points.application.member_access_resolver import MemberAccessResolver
from bounded_contexts.reward_points.domain.exceptions import PointEntryNotFoundError
from bounded_contexts.reward_points.domain.repositories.point_entry_repository import IPointEntryRepository


class DeletePointEntryUseCase:
    def __init__(self, access: MemberAccessResolver, entries: IPointEntryRepository) -> None:
        self._access = access
        self._entries = entries

    def execute(self, *, member_id: int, entry_id: int, user_id: int) -> None:
        self._access.require_manage(member_id=member_id, user_id=user_id)
        if not self._entries.delete(member_id=member_id, entry_id=entry_id):
            raise PointEntryNotFoundError


__all__ = ["DeletePointEntryUseCase"]
