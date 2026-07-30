"""``IShareTargetDirectory`` の SQLAlchemy 実装。

共有相手はアプリ共通のユーザー（``shared/infrastructure/models/user.py``）。
このコンテキストが必要とするのは「メールで 1 件引く」「ID から表示名を引く」だけで、
一覧を配る口は用意しない。無効化されたアカウント（``is_active`` が偽）は共有先に
選べない — ログインできない相手へ渡しても意味が無い。
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence

from sqlalchemy import select
from sqlalchemy.orm import Session

from bounded_contexts.reward_points.domain.repositories.share_target_directory import (
    IShareTargetDirectory,
    ShareTarget,
)
from shared.infrastructure.models import User


class SqlShareTargetDirectory(IShareTargetDirectory):
    def __init__(self, session: Session) -> None:
        self._session = session

    def find_by_email(self, email: str) -> ShareTarget | None:
        row = self._session.scalar(select(User).where(User.email == email, User.is_active))
        return _to_target(row) if row else None

    def describe(self, user_ids: Sequence[int]) -> Mapping[int, ShareTarget]:
        if not user_ids:
            return {}
        rows = self._session.scalars(select(User).where(User.id.in_(user_ids))).all()
        return {row.id: _to_target(row) for row in rows}


def _to_target(row: User) -> ShareTarget:
    return ShareTarget(user_id=row.id, email=row.email, username=row.username)


__all__ = ["SqlShareTargetDirectory"]
