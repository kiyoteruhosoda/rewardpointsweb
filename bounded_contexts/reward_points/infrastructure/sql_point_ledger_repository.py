"""``IPointLedgerRepository`` の SQLAlchemy 実装。"""

from __future__ import annotations

from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from bounded_contexts.reward_points.domain.entities.point_ledger import PointLedger
from bounded_contexts.reward_points.domain.repositories.point_ledger_repository import IPointLedgerRepository
from bounded_contexts.reward_points.infrastructure.reward_points_models import PointLedgerModel


class SqlPointLedgerRepository(IPointLedgerRepository):
    def __init__(self, session: Session) -> None:
        self._session = session

    def add(self, *, family_id: int, membership_id: int) -> PointLedger:
        row = PointLedgerModel(family_id=family_id, membership_id=membership_id)
        self._session.add(row)
        self._session.flush()
        return _to_ledger(row)

    def find_by_id(self, ledger_id: int) -> PointLedger | None:
        row = self._session.get(PointLedgerModel, ledger_id)
        return _to_ledger(row) if row else None

    def find_by_membership(self, membership_id: int) -> PointLedger | None:
        row = self._session.scalar(select(PointLedgerModel).where(PointLedgerModel.membership_id == membership_id))
        return _to_ledger(row) if row else None

    def list_for_family(self, family_id: int) -> list[PointLedger]:
        rows = self._session.scalars(
            select(PointLedgerModel).where(PointLedgerModel.family_id == family_id).order_by(PointLedgerModel.id)
        ).all()
        return [_to_ledger(row) for row in rows]

    def delete(self, ledger_id: int) -> None:
        self._session.execute(delete(PointLedgerModel).where(PointLedgerModel.id == ledger_id))


def _to_ledger(row: PointLedgerModel) -> PointLedger:
    return PointLedger(
        id=row.id,
        family_id=row.family_id,
        membership_id=row.membership_id,
        created_at=row.created_at,
    )


__all__ = ["SqlPointLedgerRepository"]
