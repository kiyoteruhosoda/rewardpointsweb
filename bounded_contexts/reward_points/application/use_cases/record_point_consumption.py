"""ポイントを消費する（要 ``MANAGE``）。

残高が足りなくても記録は拒まない。実際の運用では「先に景品を渡してから記録する」
順序が起こり得るし、残高は履歴から導出されるので負の残高もそのまま表せる。
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from bounded_contexts.reward_points.application.dto.point_entry_dto import PointEntryDTO
from bounded_contexts.reward_points.application.member_access_resolver import MemberAccessResolver
from bounded_contexts.reward_points.domain.repositories.point_entry_repository import IPointEntryRepository
from shared.kernel.timestamps import as_naive_utc, utcnow


@dataclass(frozen=True, kw_only=True)
class RecordPointConsumptionCommand:
    member_id: int
    user_id: int
    points: int
    application: str
    occurred_at: datetime | None


class RecordPointConsumptionUseCase:
    def __init__(self, access: MemberAccessResolver, entries: IPointEntryRepository) -> None:
        self._access = access
        self._entries = entries

    def execute(self, command: RecordPointConsumptionCommand) -> PointEntryDTO:
        self._access.require_manage(member_id=command.member_id, user_id=command.user_id)
        entry = self._entries.add_consumption(
            member_id=command.member_id,
            occurred_at=as_naive_utc(command.occurred_at) if command.occurred_at else utcnow(),
            points=command.points,
            application=command.application,
            recorded_by_user_id=command.user_id,
        )
        return PointEntryDTO.of(entry)


__all__ = ["RecordPointConsumptionCommand", "RecordPointConsumptionUseCase"]
