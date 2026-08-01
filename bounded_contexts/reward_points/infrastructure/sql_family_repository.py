"""``IFamilyRepository`` の SQLAlchemy 実装。"""

from __future__ import annotations

from collections.abc import Sequence

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from bounded_contexts.reward_points.domain.entities.family import Family
from bounded_contexts.reward_points.domain.repositories.family_repository import IFamilyRepository
from bounded_contexts.reward_points.domain.value_objects.family_name import FamilyName
from bounded_contexts.reward_points.domain.value_objects.family_role import FamilyRole
from bounded_contexts.reward_points.infrastructure.reward_points_models import (
    FamilyMembershipModel,
    FamilyModel,
)


class SqlFamilyRepository(IFamilyRepository):
    def __init__(self, session: Session) -> None:
        self._session = session

    def add(self, *, name: str) -> Family:
        validated = FamilyName(name)  # ドメイン不変条件を書き込み前に強制する
        row = FamilyModel(name=validated.value)
        self._session.add(row)
        self._session.flush()
        return _to_family(row)

    def find_by_id(self, family_id: int) -> Family | None:
        row = self._session.get(FamilyModel, family_id)
        return _to_family(row) if row else None

    def list_by_ids(self, family_ids: Sequence[int]) -> list[Family]:
        if not family_ids:
            return []
        rows = self._session.scalars(
            select(FamilyModel).where(FamilyModel.id.in_(family_ids)).order_by(FamilyModel.name, FamilyModel.id)
        ).all()
        return [_to_family(row) for row in rows]

    def count_owned_by(self, account_id: int) -> int:
        total = self._session.scalar(
            select(func.count())
            .select_from(FamilyMembershipModel)
            .where(
                FamilyMembershipModel.account_id == account_id,
                FamilyMembershipModel.role == FamilyRole.OWNER.value,
            )
        )
        return total or 0


def _to_family(row: FamilyModel) -> Family:
    return Family(id=row.id, name=FamilyName(row.name), created_at=row.created_at)


__all__ = ["SqlFamilyRepository"]
