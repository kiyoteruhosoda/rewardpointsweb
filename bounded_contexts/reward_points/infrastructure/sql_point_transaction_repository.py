"""``IPointTransactionRepository`` の SQLAlchemy 実装。

追記専用のため更新・行単位の削除は実装しない（ADR-0010。台帳ごと消す
``delete_by_ledger`` だけが独立時の例外 — ADR-0014）。冪等キーの衝突は
「先に引いて、無ければ書く」で扱い、同時実行で UNIQUE 制約に当たった場合も
既存行を返す（並行して同じキーが届いたのなら、望まれているのは 1 行だけ）。
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence

from sqlalchemy import delete, func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from bounded_contexts.reward_points.domain.entities.point_transaction import PointTransaction
from bounded_contexts.reward_points.domain.repositories.point_transaction_repository import (
    IPointTransactionRepository,
    NewTransaction,
)
from bounded_contexts.reward_points.domain.value_objects.idempotency_key import IdempotencyKey
from bounded_contexts.reward_points.domain.value_objects.point_amount import PointAmount
from bounded_contexts.reward_points.domain.value_objects.transaction_reason import TransactionReason
from bounded_contexts.reward_points.infrastructure.reward_points_models import (
    PointLedgerModel,
    PointTransactionModel,
)


class SqlPointTransactionRepository(IPointTransactionRepository):
    def __init__(self, session: Session) -> None:
        self._session = session

    def list_by_ledger(self, ledger_id: int) -> list[PointTransaction]:
        rows = self._session.scalars(
            select(PointTransactionModel)
            .where(PointTransactionModel.ledger_id == ledger_id)
            .order_by(PointTransactionModel.occurred_at.desc(), PointTransactionModel.id.desc())
        ).all()
        return [_to_transaction(row) for row in rows]

    def list_by_ledgers(self, ledger_ids: Sequence[int]) -> Mapping[int, list[PointTransaction]]:
        if not ledger_ids:
            return {}
        rows = self._session.scalars(
            select(PointTransactionModel)
            .where(PointTransactionModel.ledger_id.in_(ledger_ids))
            .order_by(PointTransactionModel.occurred_at.desc(), PointTransactionModel.id.desc())
        ).all()
        grouped: dict[int, list[PointTransaction]] = {ledger_id: [] for ledger_id in ledger_ids}
        for row in rows:
            grouped[row.ledger_id].append(_to_transaction(row))
        return grouped

    def find_in_ledger(self, *, ledger_id: int, transaction_id: int) -> PointTransaction | None:
        # ledger_id も条件に入れる。ID だけで引けると、閲覧権のある台帳経由で
        # 他の台帳のレコードを指せてしまう。
        row = self._session.scalar(
            select(PointTransactionModel).where(
                PointTransactionModel.id == transaction_id,
                PointTransactionModel.ledger_id == ledger_id,
            )
        )
        return _to_transaction(row) if row else None

    def find_reversal_of(self, transaction_id: int) -> PointTransaction | None:
        row = self._session.scalar(
            select(PointTransactionModel).where(PointTransactionModel.reversal_of_id == transaction_id)
        )
        return _to_transaction(row) if row else None

    def append(self, new_transaction: NewTransaction) -> PointTransaction:
        ledger_id = new_transaction.ledger_id
        key = IdempotencyKey(new_transaction.idempotency_key)
        existing = self._find_by_key(ledger_id=ledger_id, key=key.value)
        if existing is not None:
            return existing

        row = PointTransactionModel(
            ledger_id=ledger_id,
            amount=PointAmount(new_transaction.amount).value,
            reason=TransactionReason(new_transaction.reason).value,
            granted_by_membership_id=new_transaction.granted_by_membership_id,
            occurred_at=new_transaction.occurred_at,
            idempotency_key=key.value,
            reversal_of_id=new_transaction.reversal_of_id,
        )
        try:
            # SAVEPOINT の中で書く。衝突しても巻き戻るのはこの 1 行だけで、
            # 同じリクエストの他の書き込みは失われない。
            with self._session.begin_nested():
                self._session.add(row)
        except IntegrityError:
            duplicated = self._find_by_key(ledger_id=ledger_id, key=key.value)
            if duplicated is None:
                raise
            return duplicated
        return _to_transaction(row)

    def count_by_ledger(self, ledger_id: int) -> int:
        total = self._session.scalar(
            select(func.count()).select_from(PointTransactionModel).where(PointTransactionModel.ledger_id == ledger_id)
        )
        return total or 0

    def delete_by_ledger(self, ledger_id: int) -> None:
        # 打ち消し行から先に消す。reversal_of_id の自己参照外部キーに ON DELETE が
        # 無いため、元の行を先に消すと参照が残って拒まれる。
        self._session.execute(
            delete(PointTransactionModel).where(
                PointTransactionModel.ledger_id == ledger_id,
                PointTransactionModel.reversal_of_id.is_not(None),
            )
        )
        self._session.execute(delete(PointTransactionModel).where(PointTransactionModel.ledger_id == ledger_id))

    def frequent_reasons(self, *, family_id: int, limit: int) -> list[str]:
        occurrences = func.count().label("occurrences")
        rows = self._session.execute(
            select(PointTransactionModel.reason, occurrences)
            .join(PointLedgerModel, PointLedgerModel.id == PointTransactionModel.ledger_id)
            .where(
                PointLedgerModel.family_id == family_id,
                # 打ち消しは元の理由をそのまま引き継ぐので、数えると二重になる
                PointTransactionModel.reversal_of_id.is_(None),
            )
            .group_by(PointTransactionModel.reason)
            # 同数のときは文字列順。並びが実行のたびに変わらないようにする
            .order_by(occurrences.desc(), PointTransactionModel.reason)
            .limit(limit)
        ).all()
        return [str(row[0]) for row in rows]

    def _find_by_key(self, *, ledger_id: int, key: str) -> PointTransaction | None:
        row = self._session.scalar(
            select(PointTransactionModel).where(
                PointTransactionModel.ledger_id == ledger_id,
                PointTransactionModel.idempotency_key == key,
            )
        )
        return _to_transaction(row) if row else None


def _to_transaction(row: PointTransactionModel) -> PointTransaction:
    return PointTransaction(
        id=row.id,
        ledger_id=row.ledger_id,
        amount=PointAmount(row.amount),
        reason=TransactionReason(row.reason),
        granted_by_membership_id=row.granted_by_membership_id,
        occurred_at=row.occurred_at,
        created_at=row.created_at,
        reversal_of_id=row.reversal_of_id,
    )


__all__ = ["SqlPointTransactionRepository"]
