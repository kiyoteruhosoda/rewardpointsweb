"""SQLAlchemy implementation of ``IRewardEventRepository`` (ADR-0042).

One row per sticker; ``UNIQUE (event_id, number)`` prevents placing it twice. When two
parents place the same number at once, the loser hits the unique constraint. Instead of a 500
we then return "already placed" (the same shape as the ledger append
``SqlPointTransactionRepository.append``).
"""

from __future__ import annotations

from collections import defaultdict
from collections.abc import Sequence
from datetime import date, datetime

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
            deadline=new_event.deadline,
        )
        self._session.add(row)
        self._session.flush()
        # Return through the value object (the domain enforces the same invariant as the column CHECK)
        return self._to_events([row])[0]

    def stick(self, *, event_id: int, number: int, stuck_at: datetime, stuck_by_membership_id: int) -> bool:
        row = RewardEventStickerModel(
            event_id=event_id,
            number=number,
            stuck_at=stuck_at,
            stuck_by_membership_id=stuck_by_membership_id,
        )
        try:
            # Write inside a SAVEPOINT. On a conflict only this one row is rolled back
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

    def change_deadline(self, *, event_id: int, deadline: date | None) -> None:
        row = self._session.get(RewardEventModel, event_id)
        if row is None:
            return
        row.deadline = deadline
        self._session.flush()

    def delete(self, event_id: int) -> None:
        self._session.execute(delete(RewardEventModel).where(RewardEventModel.id == event_id))

    def _to_events(self, rows: Sequence[RewardEventModel]) -> list[RewardEvent]:
        """Fetch stickers in one query regardless of the number of events."""
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
                deadline=row.deadline,
            )
            for row in rows
        ]


__all__ = ["SqlRewardEventRepository"]
