"""ポイントを加算する（要 ``MANAGE``）。"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from bounded_contexts.reward_points.application.dto.point_entry_dto import PointEntryDTO
from bounded_contexts.reward_points.application.member_access_resolver import MemberAccessResolver
from bounded_contexts.reward_points.domain.repositories.point_entry_repository import IPointEntryRepository
from shared.kernel.timestamps import as_naive_utc, utcnow


@dataclass(frozen=True, kw_only=True)
class RecordPointAdditionCommand:
    member_id: int
    user_id: int
    points: int
    reason: str
    occurred_at: datetime | None


class RecordPointAdditionUseCase:
    def __init__(self, access: MemberAccessResolver, entries: IPointEntryRepository) -> None:
        self._access = access
        self._entries = entries

    def execute(self, command: RecordPointAdditionCommand) -> PointEntryDTO:
        self._access.require_manage(member_id=command.member_id, user_id=command.user_id)
        entry = self._entries.add_addition(
            member_id=command.member_id,
            occurred_at=as_naive_utc(command.occurred_at) if command.occurred_at else utcnow(),
            points=command.points,
            reason=command.reason,
            recorded_by_user_id=command.user_id,
        )
        return PointEntryDTO.of(entry)


__all__ = ["RecordPointAdditionCommand", "RecordPointAdditionUseCase"]
