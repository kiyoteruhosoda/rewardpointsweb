"""``IMemberRepository`` の SQLAlchemy 実装。"""

from __future__ import annotations

from sqlalchemy import delete, func, or_, select
from sqlalchemy.orm import Session

from bounded_contexts.reward_points.domain.entities.member import Member
from bounded_contexts.reward_points.domain.repositories.member_repository import IMemberRepository
from bounded_contexts.reward_points.domain.value_objects.member_name import MemberName
from bounded_contexts.reward_points.infrastructure.reward_points_models import (
    MemberModel,
    MemberShareModel,
    PointEntryModel,
)


class SqlMemberRepository(IMemberRepository):
    def __init__(self, session: Session) -> None:
        self._session = session

    def add(self, *, name: str, owner_user_id: int, linked_user_id: int | None) -> Member:
        validated = MemberName(name)  # ドメイン不変条件を書き込み前に強制する
        row = MemberModel(name=validated.value, owner_user_id=owner_user_id, linked_user_id=linked_user_id)
        self._session.add(row)
        self._session.flush()
        return _to_member(row)

    def find_by_id(self, member_id: int) -> Member | None:
        row = self._session.get(MemberModel, member_id)
        return _to_member(row) if row else None

    def find_by_linked_user(self, user_id: int) -> Member | None:
        row = self._session.scalar(select(MemberModel).where(MemberModel.linked_user_id == user_id))
        return _to_member(row) if row else None

    def find_reachable_by(self, user_id: int) -> list[Member]:
        shared_member_ids = select(MemberShareModel.member_id).where(MemberShareModel.user_id == user_id)
        rows = self._session.scalars(
            select(MemberModel)
            .where(
                or_(
                    MemberModel.owner_user_id == user_id,
                    MemberModel.linked_user_id == user_id,
                    MemberModel.id.in_(shared_member_ids),
                )
            )
            .order_by(MemberModel.name, MemberModel.id)
        ).all()
        return [_to_member(row) for row in rows]

    def count_owned_by(self, user_id: int) -> int:
        total = self._session.scalar(
            select(func.count()).select_from(MemberModel).where(MemberModel.owner_user_id == user_id)
        )
        return total or 0

    def delete(self, member_id: int) -> None:
        # SQLite では外部キーの ON DELETE CASCADE が既定で働かない（PRAGMA 未設定）
        # ため、子行は明示的に消す。どのバックエンドでも同じ結果になる。
        self._session.execute(delete(PointEntryModel).where(PointEntryModel.member_id == member_id))
        self._session.execute(delete(MemberShareModel).where(MemberShareModel.member_id == member_id))
        self._session.execute(delete(MemberModel).where(MemberModel.id == member_id))


def _to_member(row: MemberModel) -> Member:
    return Member(
        id=row.id,
        name=MemberName(row.name),
        owner_user_id=row.owner_user_id,
        linked_user_id=row.linked_user_id,
        created_at=row.created_at,
    )


__all__ = ["SqlMemberRepository"]
