"""``IFamilyMembershipRepository`` の SQLAlchemy 実装。"""

from __future__ import annotations

from collections.abc import Sequence
from datetime import datetime

from sqlalchemy import delete, func, select
from sqlalchemy.orm import Session

from bounded_contexts.reward_points.domain.entities.family_membership import FamilyMembership
from bounded_contexts.reward_points.domain.exceptions import MembershipNotFoundError
from bounded_contexts.reward_points.domain.repositories.family_membership_repository import (
    IFamilyMembershipRepository,
)
from bounded_contexts.reward_points.domain.value_objects.display_name import DisplayName
from bounded_contexts.reward_points.domain.value_objects.family_role import FamilyRole
from bounded_contexts.reward_points.infrastructure.reward_points_models import FamilyMembershipModel

# 一覧の並びは「親が先、次に子、同じ立場なら家族が決めた並び順、それも同じなら
# 作られた順」。並びは 1 か所で決めるので、どの画面でも家族の見え方が揃う。
_ROLE_ORDER = {FamilyRole.OWNER.value: 0, FamilyRole.PARENT.value: 1, FamilyRole.CHILD.value: 2}


class SqlFamilyMembershipRepository(IFamilyMembershipRepository):
    def __init__(self, session: Session) -> None:
        self._session = session

    def add(
        self,
        *,
        family_id: int,
        account_id: int | None,
        role: FamilyRole,
        display_name: str,
    ) -> FamilyMembership:
        validated = DisplayName(display_name)
        row = FamilyMembershipModel(
            family_id=family_id,
            account_id=account_id,
            role=role.value,
            display_name=validated.value,
            display_order=self._next_display_order(family_id),
        )
        self._session.add(row)
        self._session.flush()
        return _to_membership(row)

    def find_by_id(self, membership_id: int) -> FamilyMembership | None:
        row = self._session.get(FamilyMembershipModel, membership_id)
        return _to_membership(row) if row else None

    def find_in_family(self, *, family_id: int, account_id: int) -> FamilyMembership | None:
        row = self._session.scalar(
            select(FamilyMembershipModel).where(
                FamilyMembershipModel.family_id == family_id,
                FamilyMembershipModel.account_id == account_id,
            )
        )
        return _to_membership(row) if row else None

    def list_for_family(self, family_id: int) -> list[FamilyMembership]:
        return _sorted([_to_membership(row) for row in self._rows_of(family_id)])

    def list_for_account(self, account_id: int) -> list[FamilyMembership]:
        rows = self._session.scalars(
            select(FamilyMembershipModel)
            .where(FamilyMembershipModel.account_id == account_id)
            .order_by(FamilyMembershipModel.family_id)
        ).all()
        return [_to_membership(row) for row in rows]

    def list_by_ids(self, membership_ids: Sequence[int]) -> list[FamilyMembership]:
        if not membership_ids:
            return []
        rows = self._session.scalars(
            select(FamilyMembershipModel).where(FamilyMembershipModel.id.in_(membership_ids))
        ).all()
        return _sorted([_to_membership(row) for row in rows])

    def link_account(self, *, membership_id: int, account_id: int) -> FamilyMembership:
        row = self._require(membership_id)
        row.account_id = account_id
        self._session.flush()
        return _to_membership(row)

    def update_display_name(self, *, membership_id: int, display_name: str) -> FamilyMembership:
        row = self._require(membership_id)
        row.display_name = DisplayName(display_name).value
        self._session.flush()
        return _to_membership(row)

    def update_role(self, *, membership_id: int, role: FamilyRole) -> FamilyMembership:
        row = self._require(membership_id)
        row.role = role.value
        self._session.flush()
        return _to_membership(row)

    def propose_independence(self, *, membership_id: int, proposed_at: datetime) -> FamilyMembership:
        row = self._require(membership_id)
        row.independence_proposed_at = proposed_at
        self._session.flush()
        return _to_membership(row)

    def clear_independence_proposal(self, membership_id: int) -> FamilyMembership:
        row = self._require(membership_id)
        row.independence_proposed_at = None
        self._session.flush()
        return _to_membership(row)

    def reorder(self, *, family_id: int, membership_ids: Sequence[int]) -> None:
        rows = {row.id: row for row in self._rows_of(family_id)}
        for order, membership_id in enumerate(membership_ids):
            row = rows.get(membership_id)
            if row is None:
                raise MembershipNotFoundError
            row.display_order = order
        self._session.flush()

    def delete(self, membership_id: int) -> None:
        self._session.execute(delete(FamilyMembershipModel).where(FamilyMembershipModel.id == membership_id))

    def _rows_of(self, family_id: int) -> Sequence[FamilyMembershipModel]:
        return self._session.scalars(
            select(FamilyMembershipModel).where(FamilyMembershipModel.family_id == family_id)
        ).all()

    def _next_display_order(self, family_id: int) -> int:
        """末尾に置く。新しく加わった人が既存の並びに割り込まないようにする。"""
        highest = self._session.scalar(
            select(func.max(FamilyMembershipModel.display_order)).where(FamilyMembershipModel.family_id == family_id)
        )
        return 0 if highest is None else highest + 1

    def _require(self, membership_id: int) -> FamilyMembershipModel:
        row = self._session.get(FamilyMembershipModel, membership_id)
        if row is None:
            raise MembershipNotFoundError
        return row


def _sorted(memberships: list[FamilyMembership]) -> list[FamilyMembership]:
    return sorted(memberships, key=lambda m: (_ROLE_ORDER.get(m.role.value, 9), m.display_order, m.id))


def _to_membership(row: FamilyMembershipModel) -> FamilyMembership:
    return FamilyMembership(
        id=row.id,
        family_id=row.family_id,
        account_id=row.account_id,
        role=FamilyRole(row.role),
        display_name=DisplayName(row.display_name),
        created_at=row.created_at,
        independence_proposed_at=row.independence_proposed_at,
        display_order=row.display_order,
    )


__all__ = ["SqlFamilyMembershipRepository"]
