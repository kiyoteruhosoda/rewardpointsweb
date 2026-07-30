"""reward_points コンテキストの SQLAlchemy モデル。

Alembic が認識できるよう ``migrations/env.py`` へ import を追加してある。
種別・共有範囲は DB ネイティブ ENUM を使わず ``native_enum=False``（CHECK 制約付き
VARCHAR）で持つ（CLAUDE.md「DB モデリング」）。
"""

from __future__ import annotations

import sqlalchemy as sa
from sqlalchemy.orm import Mapped, mapped_column

from shared.infrastructure.models.base import BigIntPk, utcnow
from shared.kernel.database.db import Base

POINT_ENTRY_TYPE = sa.Enum("addition", "consumption", name="point_entry_type", native_enum=False)
MEMBER_ACCESS_LEVEL = sa.Enum("view", "manage", name="member_access_level", native_enum=False)


class MemberModel(Base):
    __tablename__ = "members"

    id: Mapped[int] = mapped_column(BigIntPk, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(sa.String(100), nullable=False)
    owner_user_id: Mapped[int] = mapped_column(BigIntPk, sa.ForeignKey("users.id"), nullable=False, index=True)
    # 1 つのアカウントが「自分のポイント」として見られるメンバーは 1 人だけ。
    # アカウントが消えてもメンバーは残す（本人ログインの紐付けだけが外れる）。
    linked_user_id: Mapped[int | None] = mapped_column(
        BigIntPk, sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True, unique=True
    )
    created_at = mapped_column(sa.DateTime(), nullable=False, default=utcnow)
    updated_at = mapped_column(sa.DateTime(), nullable=False, default=utcnow, onupdate=utcnow)


class MemberShareModel(Base):
    __tablename__ = "member_shares"

    member_id: Mapped[int] = mapped_column(BigIntPk, sa.ForeignKey("members.id", ondelete="CASCADE"), primary_key=True)
    # 共有先のアカウントが消えれば、その共有はもう意味を持たない
    user_id: Mapped[int] = mapped_column(BigIntPk, sa.ForeignKey("users.id", ondelete="CASCADE"), primary_key=True)
    access_level: Mapped[str] = mapped_column(MEMBER_ACCESS_LEVEL, nullable=False)
    created_at = mapped_column(sa.DateTime(), nullable=False, default=utcnow)


class PointEntryModel(Base):
    __tablename__ = "point_entries"

    id: Mapped[int] = mapped_column(BigIntPk, primary_key=True, autoincrement=True)
    member_id: Mapped[int] = mapped_column(
        BigIntPk, sa.ForeignKey("members.id", ondelete="CASCADE"), nullable=False, index=True
    )
    entry_type: Mapped[str] = mapped_column(POINT_ENTRY_TYPE, nullable=False)
    occurred_at = mapped_column(sa.DateTime(), nullable=False)
    points: Mapped[int] = mapped_column(sa.Integer(), nullable=False)
    # 加算なら理由、消費なら用途。種別によって片方だけが埋まる
    reason: Mapped[str | None] = mapped_column(sa.String(255), nullable=True)
    application: Mapped[str | None] = mapped_column(sa.String(255), nullable=True)
    # 記録した人のアカウントが消えても履歴は残す（履歴はメンバーのもので、
    # 記録者のものではない）。誰が記録したか分からなくなるだけ。
    recorded_by_user_id: Mapped[int | None] = mapped_column(
        BigIntPk, sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    created_at = mapped_column(sa.DateTime(), nullable=False, default=utcnow)
    updated_at = mapped_column(sa.DateTime(), nullable=False, default=utcnow, onupdate=utcnow)


__all__ = [
    "MEMBER_ACCESS_LEVEL",
    "POINT_ENTRY_TYPE",
    "MemberModel",
    "MemberShareModel",
    "PointEntryModel",
]
