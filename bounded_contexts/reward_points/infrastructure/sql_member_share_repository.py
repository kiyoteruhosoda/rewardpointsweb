"""``IMemberShareRepository`` の SQLAlchemy 実装。"""

from __future__ import annotations

from collections.abc import Sequence

from sqlalchemy import select
from sqlalchemy.orm import Session

from bounded_contexts.reward_points.domain.entities.member_share import MemberShare
from bounded_contexts.reward_points.domain.repositories.member_share_repository import IMemberShareRepository
from bounded_contexts.reward_points.domain.value_objects.member_access_level import MemberAccessLevel
from bounded_contexts.reward_points.infrastructure.reward_points_models import MemberShareModel


class SqlMemberShareRepository(IMemberShareRepository):
    def __init__(self, session: Session) -> None:
        self._session = session

    def list_for_member(self, member_id: int) -> list[MemberShare]:
        rows = self._session.scalars(
            select(MemberShareModel).where(MemberShareModel.member_id == member_id).order_by(MemberShareModel.user_id)
        ).all()
        return [_to_share(row) for row in rows]

    def list_for_user(self, user_id: int) -> list[MemberShare]:
        rows = self._session.scalars(
            select(MemberShareModel).where(MemberShareModel.user_id == user_id).order_by(MemberShareModel.member_id)
        ).all()
        return [_to_share(row) for row in rows]

    def list_for_members(self, member_ids: Sequence[int]) -> list[MemberShare]:
        if not member_ids:
            return []
        rows = self._session.scalars(
            select(MemberShareModel)
            .where(MemberShareModel.member_id.in_(member_ids))
            .order_by(MemberShareModel.member_id, MemberShareModel.user_id)
        ).all()
        return [_to_share(row) for row in rows]

    def grant(self, *, member_id: int, user_id: int, level: MemberAccessLevel) -> MemberShare:
        row = MemberShareModel(member_id=member_id, user_id=user_id, access_level=level.value)
        self._session.add(row)
        self._session.flush()
        return _to_share(row)

    def revoke(self, *, member_id: int, user_id: int) -> bool:
        row = self._session.get(MemberShareModel, (member_id, user_id))
        if row is None:
            return False
        self._session.delete(row)
        return True


def _to_share(row: MemberShareModel) -> MemberShare:
    return MemberShare(
        member_id=row.member_id,
        user_id=row.user_id,
        level=MemberAccessLevel(row.access_level),
    )


__all__ = ["SqlMemberShareRepository"]
