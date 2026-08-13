"""``IFamilyRepository`` の SQLAlchemy 実装。"""

from __future__ import annotations

from collections.abc import Sequence

from sqlalchemy import delete, func, select
from sqlalchemy.orm import Session

from bounded_contexts.reward_points.domain.entities.family import Family
from bounded_contexts.reward_points.domain.exceptions import FamilyNotFoundError
from bounded_contexts.reward_points.domain.repositories.family_repository import IFamilyRepository
from bounded_contexts.reward_points.domain.value_objects.family_name import FamilyName
from bounded_contexts.reward_points.domain.value_objects.family_role import FamilyRole
from bounded_contexts.reward_points.domain.value_objects.family_rules import FamilyRules
from bounded_contexts.reward_points.infrastructure.reward_points_models import (
    FamilyMembershipModel,
    FamilyModel,
)


class SqlFamilyRepository(IFamilyRepository):
    def __init__(self, session: Session) -> None:
        self._session = session

    def add(self, *, name: str, rules: str | None = None) -> Family:
        validated = FamilyName(name)  # ドメイン不変条件を書き込み前に強制する
        row = FamilyModel(name=validated.value, rules=_validated_rules(rules))
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

    def update_name(self, *, family_id: int, name: str) -> Family:
        validated = FamilyName(name)  # ドメイン不変条件を書き込み前に強制する
        row = self._session.get(FamilyModel, family_id)
        if row is None:
            raise FamilyNotFoundError
        row.name = validated.value
        self._session.flush()
        return _to_family(row)

    def update_rules(self, *, family_id: int, rules: str | None) -> Family:
        validated = _validated_rules(rules)  # ドメイン不変条件を書き込み前に強制する
        row = self._session.get(FamilyModel, family_id)
        if row is None:
            raise FamilyNotFoundError
        row.rules = validated
        self._session.flush()
        return _to_family(row)

    def delete(self, family_id: int) -> None:
        # 参加・招待・台帳は外部キーの ON DELETE CASCADE で家族と一緒に消える
        self._session.execute(delete(FamilyModel).where(FamilyModel.id == family_id))

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


def _validated_rules(rules: str | None) -> str | None:
    """空・空白だけの入力は「書いていない」として NULL に寄せる（ADR-0027）。

    残しておくと、画面には何も出ないのに「ルールあり」の家族が生まれる。
    """
    if rules is None or not rules.strip():
        return None
    return FamilyRules(rules).value


def _to_family(row: FamilyModel) -> Family:
    return Family(
        id=row.id,
        name=FamilyName(row.name),
        rules=FamilyRules(row.rules) if row.rules else None,
        created_at=row.created_at,
    )


__all__ = ["SqlFamilyRepository"]
