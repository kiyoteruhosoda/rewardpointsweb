"""``IDailyBonusRepository`` の SQLAlchemy 実装（ADR-0024）。

台帳につき 1 件（``UNIQUE (ledger_id)``）なので、保存は「引いて、あれば書き換え、
無ければ足す」で足りる。ただし「引いた時点では無かった」が最後まで正しいとは
限らない — 2 人の親が同時に最初の設定を送ると、どちらの側からも行が見えないまま
両方が足しに行く。負けた側は一意制約に当たるので、そこで勝った行を読み直して
書き換える（``PUT`` は置き換えなので、どちらが勝っても結果は同じで良い）。
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
        # 値オブジェクトを先に通す。列の CHECK と同じ不変条件をドメイン側でも守る
        amount = PointAmount(draft.amount)
        reason = TransactionReason(draft.reason)
        row = self._find_row(draft.ledger_id) or self._add_row(draft, amount=amount, reason=reason)
        # 量と理由はどちらの経路でも最後に書く（同時に作られた行を掴んだ場合も、
        # この呼び出しの内容で置き換わる）。starts_on / granted_through は動かさない
        # — 量を直しただけで、渡し終えた日まで無かったことにはしない
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

    def _add_row(self, draft: DailyBonusDraft, *, amount: PointAmount, reason: TransactionReason) -> DailyBonusModel:
        """行を足す。同時に足されていたら、その行を返す。

        ``UNIQUE (ledger_id)`` に当たった側が 500 で終わらないようにするための
        分岐で、台帳への追記（``SqlPointTransactionRepository.append``）と同じ形。
        """
        row = DailyBonusModel(
            ledger_id=draft.ledger_id,
            amount=amount.value,
            reason=reason.value,
            starts_on=draft.starts_on,
            granted_through=None,
        )
        try:
            # SAVEPOINT の中で書く。衝突しても巻き戻るのはこの 1 行だけで、
            # 同じリクエストの他の書き込みは失われない
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
