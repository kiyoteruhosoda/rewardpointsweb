"""``IPointEntryRepository`` の SQLAlchemy 実装。"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from bounded_contexts.reward_points.domain.entities.point_entry import PointEntry
from bounded_contexts.reward_points.domain.repositories.point_entry_repository import IPointEntryRepository
from bounded_contexts.reward_points.domain.value_objects.entry_description import EntryDescription
from bounded_contexts.reward_points.domain.value_objects.point_amount import PointAmount
from bounded_contexts.reward_points.domain.value_objects.point_entry_type import PointEntryType
from bounded_contexts.reward_points.infrastructure.point_entry_mapper import to_entry
from bounded_contexts.reward_points.infrastructure.reward_points_models import PointEntryModel


@dataclass(frozen=True, kw_only=True)
class _NewEntry:
    """まだ ID を持たない履歴。

    加算と消費で違うのは種別と説明の呼び名だけで、書き込み自体は 1 か所で済む。
    その 1 か所へ渡す値をまとめて持つ（種別ごとの詰め替えを ``_add`` に閉じるため）。
    """

    member_id: int
    occurred_at: datetime
    amount: PointAmount
    entry_type: PointEntryType
    description: EntryDescription
    recorded_by_user_id: int


class SqlPointEntryRepository(IPointEntryRepository):
    def __init__(self, session: Session) -> None:
        self._session = session

    def list_by_member(self, member_id: int) -> list[PointEntry]:
        rows = self._session.scalars(
            select(PointEntryModel)
            .where(PointEntryModel.member_id == member_id)
            .order_by(PointEntryModel.occurred_at.desc(), PointEntryModel.id.desc())
        ).all()
        return [to_entry(row) for row in rows]

    def list_by_members(self, member_ids: Sequence[int]) -> Mapping[int, list[PointEntry]]:
        if not member_ids:
            return {}
        rows = self._session.scalars(
            select(PointEntryModel)
            .where(PointEntryModel.member_id.in_(member_ids))
            .order_by(PointEntryModel.occurred_at.desc(), PointEntryModel.id.desc())
        ).all()
        grouped: dict[int, list[PointEntry]] = {member_id: [] for member_id in member_ids}
        for row in rows:
            grouped[row.member_id].append(to_entry(row))
        return grouped

    def add_addition(
        self,
        *,
        member_id: int,
        occurred_at: datetime,
        points: int,
        reason: str,
        recorded_by_user_id: int,
    ) -> PointEntry:
        return self._add(
            _NewEntry(
                member_id=member_id,
                occurred_at=occurred_at,
                amount=PointAmount(points),
                entry_type=PointEntryType.ADDITION,
                description=EntryDescription(reason),
                recorded_by_user_id=recorded_by_user_id,
            )
        )

    def add_consumption(
        self,
        *,
        member_id: int,
        occurred_at: datetime,
        points: int,
        application: str,
        recorded_by_user_id: int,
    ) -> PointEntry:
        return self._add(
            _NewEntry(
                member_id=member_id,
                occurred_at=occurred_at,
                amount=PointAmount(points),
                entry_type=PointEntryType.CONSUMPTION,
                description=EntryDescription(application),
                recorded_by_user_id=recorded_by_user_id,
            )
        )

    def delete(self, *, member_id: int, entry_id: int) -> bool:
        # member_id も条件に入れる。ID だけで消せると、閲覧権のあるメンバー経由で
        # 他のメンバーの履歴を消せてしまう。
        row = self._session.scalar(
            select(PointEntryModel).where(
                PointEntryModel.id == entry_id,
                PointEntryModel.member_id == member_id,
            )
        )
        if row is None:
            return False
        self._session.delete(row)
        return True

    def _add(self, new_entry: _NewEntry) -> PointEntry:
        """ドメイン不変条件を通した値で 1 行書く（列の詰め方だけが種別で変わる）。"""
        is_addition = new_entry.entry_type is PointEntryType.ADDITION
        row = PointEntryModel(
            member_id=new_entry.member_id,
            entry_type=new_entry.entry_type.value,
            occurred_at=new_entry.occurred_at,
            points=new_entry.amount.value,
            reason=new_entry.description.value if is_addition else None,
            application=None if is_addition else new_entry.description.value,
            recorded_by_user_id=new_entry.recorded_by_user_id,
        )
        self._session.add(row)
        self._session.flush()
        return to_entry(row)


__all__ = ["SqlPointEntryRepository"]
