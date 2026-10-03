"""``IRewardEventRepository`` の SQLAlchemy 実装（ADR-0042）。

シールは 1 枚 1 行で、``UNIQUE (event_id, number)`` が二重貼りを止める。2 人の
親が同時に同じ番号を貼ると、負けた側は一意制約に当たる。そこで 500 にせず
「もう貼られていた」と返す（台帳への追記 ``SqlPointTransactionRepository.append``
と同じ形）。
"""

from __future__ import annotations

from collections import defaultdict
from collections.abc import Sequence
from datetime import datetime

from sqlalchemy import delete, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from bounded_contexts.reward_points.domain.entities.reward_event import EventSticker, RewardEvent
from bounded_contexts.reward_points.domain.repositories.reward_event_repository import (
    IRewardEventRepository,
    NewRewardEvent,
)
from bounded_contexts.reward_points.domain.value_objects.point_amount import PointAmount
from bounded_contexts.reward_points.domain.value_objects.transaction_reason import TransactionReason
from bounded_contexts.reward_points.infrastructure.reward_points_models import (
    RewardEventModel,
    RewardEventStickerModel,
)


class SqlRewardEventRepository(IRewardEventRepository):
    def __init__(self, session: Session) -> None:
        self._session = session

    def list_by_ledger(self, ledger_id: int) -> list[RewardEvent]:
        rows = self._session.scalars(
            select(RewardEventModel).where(RewardEventModel.ledger_id == ledger_id).order_by(RewardEventModel.id)
        ).all()
        return self._to_events(rows)

    def find_in_ledger(self, *, ledger_id: int, event_id: int) -> RewardEvent | None:
        row = self._session.scalar(
            select(RewardEventModel).where(RewardEventModel.id == event_id, RewardEventModel.ledger_id == ledger_id)
        )
        return self._to_events([row])[0] if row else None

    def add(self, new_event: NewRewardEvent) -> RewardEvent:
        row = RewardEventModel(
            ledger_id=new_event.ledger_id,
            title=new_event.title,
            reward_points=new_event.reward,
            goal_count=new_event.goal_count,
        )
        self._session.add(row)
        self._session.flush()
        # 値オブジェクトを通して返す（列の CHECK と同じ不変条件をドメイン側でも守る）
        return self._to_events([row])[0]

    def stick(self, *, event_id: int, number: int, stuck_at: datetime, stuck_by_membership_id: int) -> bool:
        row = RewardEventStickerModel(
            event_id=event_id,
            number=number,
            stuck_at=stuck_at,
            stuck_by_membership_id=stuck_by_membership_id,
        )
        try:
            # SAVEPOINT の中で書く。衝突しても巻き戻るのはこの 1 行だけ
            with self._session.begin_nested():
                self._session.add(row)
        except IntegrityError:
            return False
        return True

    def peel(self, *, event_id: int, number: int) -> None:
        self._session.execute(
            delete(RewardEventStickerModel).where(
                RewardEventStickerModel.event_id == event_id,
                RewardEventStickerModel.number == number,
            )
        )

    def mark_completed(self, *, event_id: int, completed_at: datetime, awarded_transaction_id: int) -> None:
        row = self._session.get(RewardEventModel, event_id)
        if row is None:
            return
        row.completed_at = completed_at
        row.awarded_transaction_id = awarded_transaction_id
        self._session.flush()

    def delete(self, event_id: int) -> None:
        self._session.execute(delete(RewardEventModel).where(RewardEventModel.id == event_id))

    def _to_events(self, rows: Sequence[RewardEventModel]) -> list[RewardEvent]:
        """シールはイベントの数によらず 1 回で引く。"""
        stickers: dict[int, list[EventSticker]] = defaultdict(list)
        if rows:
            for sticker in self._session.scalars(
                select(RewardEventStickerModel)
                .where(RewardEventStickerModel.event_id.in_([row.id for row in rows]))
                .order_by(RewardEventStickerModel.event_id, RewardEventStickerModel.number)
            ):
                stickers[sticker.event_id].append(EventSticker(number=sticker.number, stuck_at=sticker.stuck_at))
        return [
            RewardEvent(
                id=row.id,
                ledger_id=row.ledger_id,
                title=TransactionReason(row.title),
                reward=PointAmount(row.reward_points),
                goal_count=row.goal_count,
                stickers=tuple(stickers[row.id]),
                completed_at=row.completed_at,
                created_at=row.created_at,
            )
            for row in rows
        ]


__all__ = ["SqlRewardEventRepository"]
