"""SQLAlchemy implementation of ``IDailyBonusRepository`` (ADR-0024).

One per ledger (``UNIQUE (ledger_id)``), so saving is just "look it up, rewrite if present,
add if not". But "it was absent when looked up" may not stay true — if two parents send
the first setting simultaneously, both go to add without seeing the other's row. The loser
hits the unique constraint, so it re-reads the winning row and rewrites it (``PUT`` is a
replacement, so the result may be the same whichever wins).
"""

from __future__ import annotations

from collections.abc import Sequence
from datetime import date

from sqlalchemy import and_, delete, or_, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from bounded_contexts.reward_points.domain.entities.daily_bonus import DailyBonus
from bounded_contexts.reward_points.domain.repositories.daily_bonus_repository import (
    DailyBonusDraft,
    IDailyBonusRepository,
)
from bounded_contexts.reward_points.domain.value_objects.point_amount import PointAmount
from bounded_contexts.reward_points.domain.value_objects.transaction_reason import TransactionReason
from bounded_contexts.reward_points.infrastructure.reward_points_models import DailyBonusModel


class SqlDailyBonusRepository(IDailyBonusRepository):
    def __init__(self, session: Session) -> None:
        self._session = session

    def find_by_ledger(self, ledger_id: int) -> DailyBonus | None:
        row = self._find_row(ledger_id)
        return _to_bonus(row) if row else None

    def list_for_ledgers(self, ledger_ids: Sequence[int]) -> list[DailyBonus]:
        if not ledger_ids:
            return []
        rows = self._session.scalars(
            select(DailyBonusModel).where(DailyBonusModel.ledger_id.in_(ledger_ids)).order_by(DailyBonusModel.id)
        ).all()
        return [_to_bonus(row) for row in rows]

    def save(self, draft: DailyBonusDraft) -> DailyBonus:
        # Pass through value objects first. The domain enforces the same invariants as the column CHECKs
        amount = PointAmount(draft.amount)
        reason = TransactionReason(draft.reason)
        row = self._find_row(draft.ledger_id) or self._add_row(draft, amount=amount, reason=reason)
        # Amount and reason are written last on either path (even when grabbing a row created
        # concurrently, it is replaced with this call's content). starts_on / granted_through
        # are left alone — merely fixing the amount must not erase the days already granted
        row.amount = amount.value
        row.reason = reason.value
        self._session.flush()
        return _to_bonus(row)

    def delete_by_ledger(self, ledger_id: int) -> None:
        self._session.execute(delete(DailyBonusModel).where(DailyBonusModel.ledger_id == ledger_id))

    def list_due(self, today: date) -> list[DailyBonus]:
        rows = self._session.scalars(
            select(DailyBonusModel)
            .where(
                or_(
                    # Not a single day granted yet (granted once the start date arrives)
                    and_(
                        DailyBonusModel.granted_through.is_(None),
                        DailyBonusModel.starts_on <= today,
                    ),
                    DailyBonusModel.granted_through < today,
                )
            )
            .order_by(DailyBonusModel.id)
        ).all()
        return [_to_bonus(row) for row in rows]

    def mark_granted_through(self, *, bonus_id: int, day: date) -> None:
        row = self._session.get(DailyBonusModel, bonus_id)
        if row is None:
            return
        row.granted_through = day
        self._session.flush()

    def _add_row(self, draft: DailyBonusDraft, *, amount: PointAmount, reason: TransactionReason) -> DailyBonusModel:
        """Add a row. If one was added concurrently, return that row.

        This branch keeps the side hitting ``UNIQUE (ledger_id)`` from ending in a 500, the
        same shape as appending to the ledger (``SqlPointTransactionRepository.append``).
        """
        row = DailyBonusModel(
            ledger_id=draft.ledger_id,
            amount=amount.value,
            reason=reason.value,
            starts_on=draft.starts_on,
            granted_through=None,
        )
        try:
            # Write inside a SAVEPOINT. On conflict only this row is rolled back, and other
            # writes in the same request are not lost
            with self._session.begin_nested():
                self._session.add(row)
        except IntegrityError:
            won = self._find_row(draft.ledger_id)
            if won is None:
                raise
            return won
        return row

    def _find_row(self, ledger_id: int) -> DailyBonusModel | None:
        return self._session.scalar(select(DailyBonusModel).where(DailyBonusModel.ledger_id == ledger_id))


def _to_bonus(row: DailyBonusModel) -> DailyBonus:
    return DailyBonus(
        id=row.id,
        ledger_id=row.ledger_id,
        amount=PointAmount(row.amount),
        reason=TransactionReason(row.reason),
        starts_on=row.starts_on,
        granted_through=row.granted_through,
    )


__all__ = ["SqlDailyBonusRepository"]
