"""行 ↔ ドメインエンティティの変換。

種別ごとに詰める列が違う（加算は ``reason``、消費は ``application``）ため、
分岐はここ 1 か所に閉じ込める。``getattr`` による動的解決は使わない
（CLAUDE.md「動的呼び出しの制限」）。
"""

from __future__ import annotations

from bounded_contexts.reward_points.domain.entities.point_entry import (
    PointAddition,
    PointConsumption,
    PointEntry,
)
from bounded_contexts.reward_points.domain.value_objects.entry_description import EntryDescription
from bounded_contexts.reward_points.domain.value_objects.point_amount import PointAmount
from bounded_contexts.reward_points.domain.value_objects.point_entry_type import PointEntryType
from bounded_contexts.reward_points.infrastructure.reward_points_models import PointEntryModel


def to_entry(row: PointEntryModel) -> PointEntry:
    if row.entry_type == PointEntryType.ADDITION.value:
        return PointAddition(
            id=row.id,
            member_id=row.member_id,
            occurred_at=row.occurred_at,
            amount=PointAmount(row.points),
            recorded_by_user_id=row.recorded_by_user_id,
            reason=EntryDescription(_required(row.reason, column="reason", row_id=row.id)),
        )
    if row.entry_type == PointEntryType.CONSUMPTION.value:
        return PointConsumption(
            id=row.id,
            member_id=row.member_id,
            occurred_at=row.occurred_at,
            amount=PointAmount(row.points),
            recorded_by_user_id=row.recorded_by_user_id,
            application=EntryDescription(_required(row.application, column="application", row_id=row.id)),
        )
    raise ValueError(f"unknown point entry type: {row.entry_type!r} (point_entries.id={row.id})")


def _required(value: str | None, *, column: str, row_id: int) -> str:
    if value is None:
        raise ValueError(f"point_entries.{column} must not be NULL (id={row_id})")
    return value


__all__ = ["to_entry"]
