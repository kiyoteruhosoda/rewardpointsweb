"""ユーザー・パスワードリセットトークンのモデル。

ログインの識別子は ``username``（UNIQUE）で、``email`` は任意項目（ADR-0011）。
メールアドレスを持たないアカウント（子ども）を作れるようにするための分離で、
設定されている場合は従来どおり通知・パスワードリセットに使う。

``display_name`` は画面に出す名前。識別子とは別に持つので、名乗りを変えても
ログインの手順は変わらない。
"""

from __future__ import annotations

import sqlalchemy as sa
from sqlalchemy.orm import Mapped, mapped_column, relationship

from shared.infrastructure.models.base import BigIntPk, utcnow
from shared.kernel.database.db import Base

user_roles = sa.Table(
    "user_roles",
    Base.metadata,
    sa.Column("user_id", BigIntPk, sa.ForeignKey("users.id"), primary_key=True),
    sa.Column("role_id", BigIntPk, sa.ForeignKey("roles.id"), primary_key=True),
)


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(BigIntPk, primary_key=True, autoincrement=True)
    # ログイン識別子。小文字へ正規化して保存する（shared/domain/auth/username.py）
    username: Mapped[str] = mapped_column(sa.String(255), unique=True, nullable=False)
    # 任意項目。設定されていれば通知・パスワードリセットに使う
    email: Mapped[str | None] = mapped_column(sa.String(255), unique=True, nullable=True)
    display_name: Mapped[str] = mapped_column(sa.String(100), nullable=False)
    password_hash: Mapped[str] = mapped_column(sa.String(255), nullable=False)
    is_active: Mapped[bool] = mapped_column(sa.Boolean(), nullable=False, default=True, server_default=sa.true())
    # 一時パスワードでログインした状態。変更を終えるまで他の操作を許可しない
    must_change_password: Mapped[bool] = mapped_column(
        sa.Boolean(), nullable=False, default=False, server_default=sa.false()
    )
    # 一時パスワードの有効期限（通常のパスワードでは NULL）
    temporary_password_expires_at = mapped_column(sa.DateTime(), nullable=True)
    created_at = mapped_column(sa.DateTime(), nullable=False, default=utcnow)
    updated_at = mapped_column(sa.DateTime(), nullable=False, default=utcnow, onupdate=utcnow)

    roles = relationship("Role", secondary=user_roles, lazy="selectin")

    @property
    def permission_codes(self) -> frozenset[str]:
        """有効 scope = 全ロールが持つ権限の和集合。"""
        return frozenset(p.code for r in self.roles for p in r.permissions)


class PasswordResetToken(Base):
    __tablename__ = "password_reset_tokens"

    id: Mapped[int] = mapped_column(BigIntPk, primary_key=True, autoincrement=True)
    # アカウントの削除に追随して消える（拒否ではなく CASCADE。トークンは
    # 本人が居なければ意味を持たない）
    user_id: Mapped[int] = mapped_column(
        BigIntPk, sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    token_hash: Mapped[str] = mapped_column(sa.String(64), unique=True, nullable=False)
    expires_at = mapped_column(sa.DateTime(), nullable=False)
    used_at = mapped_column(sa.DateTime(), nullable=True)
    created_at = mapped_column(sa.DateTime(), nullable=False, default=utcnow)


__all__ = ["PasswordResetToken", "User", "user_roles"]
