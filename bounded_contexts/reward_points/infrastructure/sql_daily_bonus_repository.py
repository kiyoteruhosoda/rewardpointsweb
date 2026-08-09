"""``IDailyBonusRepository`` の SQLAlchemy 実装（ADR-0024）。

台帳につき 1 件（``UNIQUE (ledger_id)``）なので、保存は「引いて、あれば書き換え、
無ければ足す」で足りる。
"""

from __future__ import annotations

from datetime import date

from sqlalchemy import and_, delete, or_, select
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

    def save(self, draft: DailyBonusDraft) -> DailyBonus:
        # 値オブジェクトを先に通す。列の CHECK と同じ不変条件をドメイン側でも守る
        amount = PointAmount(draft.amount)
        reason = TransactionReason(draft.reason)
        row = self._find_row(draft.ledger_id)
        if row is None:
            row = DailyBonusModel(
                ledger_id=draft.ledger_id,
                amount=amount.value,
                reason=reason.value,
                starts_on=draft.starts_on,
                granted_through=None,
            )
            self._session.add(row)
            self._session.flush()
        else:
            # starts_on / granted_through は動かさない（量を直しただけで、
            # 渡し終えた日まで無かったことにはしない）
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
                    # まだ 1 日も渡していない（開始日が来ていれば渡す）
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
