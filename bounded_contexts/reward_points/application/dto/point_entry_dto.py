"""ポイント履歴・台帳の出力 DTO。"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from bounded_contexts.reward_points.domain.entities.point_entry import PointEntry
from bounded_contexts.reward_points.domain.value_objects.member_access_level import MemberAccessLevel
from bounded_contexts.reward_points.domain.value_objects.point_entry_type import PointEntryType


@dataclass(frozen=True, kw_only=True)
class PointEntryDTO:
    id: int
    entry_type: PointEntryType
    occurred_at: datetime
    points: int
    signed_points: int
    description: str

    @classmethod
    def of(cls, entry: PointEntry) -> PointEntryDTO:
        return cls(
            id=entry.id,
            entry_type=entry.entry_type,
            occurred_at=entry.occurred_at,
            points=entry.amount.value,
            signed_points=entry.signed_points,
            description=entry.description.value,
        )


@dataclass(frozen=True, kw_only=True)
class PointLedgerDTO:
    member_id: int
    member_name: str
    balance: int
    access_level: MemberAccessLevel
    # 共有の管理を出すかは「所有者か」で決まる（`access_level` では決まらない）
    is_owner: bool
    entries: tuple[PointEntryDTO, ...]


__all__ = ["PointEntryDTO", "PointLedgerDTO"]
