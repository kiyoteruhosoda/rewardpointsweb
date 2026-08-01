"""reward_points コンテキストの SQLAlchemy モデル。

Alembic が認識できるよう ``migrations/env.py`` へ import を追加してある。
立場（role）は DB ネイティブ ENUM を使わず ``native_enum=False``（CHECK 制約付き
VARCHAR）で持つ（CLAUDE.md「DB モデリング」）。

``point_transactions`` は追記専用（ADR-0010）。``updated_at`` を持たないのは、
更新される想定が無いことをスキーマ自身で示すため。
"""

from __future__ import annotations

import sqlalchemy as sa
from sqlalchemy.orm import Mapped, mapped_column

from shared.infrastructure.models.base import BigIntPk, utcnow
from shared.kernel.database.db import Base

FAMILY_ROLE = sa.Enum("owner", "parent", "child", name="family_role", native_enum=False)


class FamilyModel(Base):
    __tablename__ = "families"

    id: Mapped[int] = mapped_column(BigIntPk, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(sa.String(100), nullable=False)
    created_at = mapped_column(sa.DateTime(), nullable=False, default=utcnow)
    updated_at = mapped_column(sa.DateTime(), nullable=False, default=utcnow, onupdate=utcnow)


class FamilyMembershipModel(Base):
    __tablename__ = "family_memberships"
    __table_args__ = (
        # 同一 Family 内では 1 アカウント 1 membership（ADR-0009）。
        # account_id は NULL を取りうる（親が作った直後の子はまだ未紐付け）。
        # NULL 同士は衝突しないため、未紐付けの参加者は何人でも並べられる。
        sa.UniqueConstraint("family_id", "account_id", name="uq_family_memberships_family_account"),
    )

    id: Mapped[int] = mapped_column(BigIntPk, primary_key=True, autoincrement=True)
    family_id: Mapped[int] = mapped_column(
        BigIntPk, sa.ForeignKey("families.id", ondelete="CASCADE"), nullable=False, index=True
    )
    # アカウントが消えても参加と台帳は残す（本人ログインの紐付けだけが外れる）
    account_id: Mapped[int | None] = mapped_column(
        BigIntPk, sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True
    )
    role: Mapped[str] = mapped_column(FAMILY_ROLE, nullable=False)
    display_name: Mapped[str] = mapped_column(sa.String(100), nullable=False)
    created_at = mapped_column(sa.DateTime(), nullable=False, default=utcnow)
    updated_at = mapped_column(sa.DateTime(), nullable=False, default=utcnow, onupdate=utcnow)


class PointLedgerModel(Base):
    __tablename__ = "point_ledgers"

    id: Mapped[int] = mapped_column(BigIntPk, primary_key=True, autoincrement=True)
    family_id: Mapped[int] = mapped_column(
        BigIntPk, sa.ForeignKey("families.id", ondelete="CASCADE"), nullable=False, index=True
    )
    # role = child の membership と 1 対 1（ADR-0009）
    membership_id: Mapped[int] = mapped_column(
        BigIntPk,
        sa.ForeignKey("family_memberships.id", ondelete="CASCADE"),
        nullable=False,
        unique=True,
    )
    created_at = mapped_column(sa.DateTime(), nullable=False, default=utcnow)


class PointTransactionModel(Base):
    __tablename__ = "point_transactions"
    __table_args__ = (
        # 送信ボタンの二重タップで二重登録しない（ADR-0010）
        sa.UniqueConstraint("ledger_id", "idempotency_key", name="uq_point_transactions_idempotency"),
        # 同一レコードの二重取り消しを DB 制約で防ぐ
        sa.UniqueConstraint("reversal_of_id", name="uq_point_transactions_reversal_of"),
        sa.CheckConstraint("amount <> 0", name="ck_point_transactions_amount_nonzero"),
        sa.Index("ix_point_transactions_ledger_occurred", "ledger_id", "occurred_at", "id"),
    )

    id: Mapped[int] = mapped_column(BigIntPk, primary_key=True, autoincrement=True)
    ledger_id: Mapped[int] = mapped_column(
        BigIntPk, sa.ForeignKey("point_ledgers.id", ondelete="CASCADE"), nullable=False
    )
    # 符号付き。加算は正、消費は負
    amount: Mapped[int] = mapped_column(sa.Integer(), nullable=False)
    reason: Mapped[str] = mapped_column(sa.String(255), nullable=False)
    # 操作した参加者が家族を離れても記録は残す（履歴は台帳のもの）
    granted_by_membership_id: Mapped[int | None] = mapped_column(
        BigIntPk, sa.ForeignKey("family_memberships.id", ondelete="SET NULL"), nullable=True
    )
    # 出来事の発生日時（遡って入力できる）とレコード作成日時は別物
    occurred_at = mapped_column(sa.DateTime(), nullable=False)
    created_at = mapped_column(sa.DateTime(), nullable=False, default=utcnow)
    reversal_of_id: Mapped[int | None] = mapped_column(BigIntPk, sa.ForeignKey("point_transactions.id"), nullable=True)
    idempotency_key: Mapped[str] = mapped_column(sa.String(64), nullable=False)


class FamilyInvitationModel(Base):
    __tablename__ = "family_invitations"

    id: Mapped[int] = mapped_column(BigIntPk, primary_key=True, autoincrement=True)
    family_id: Mapped[int] = mapped_column(
        BigIntPk, sa.ForeignKey("families.id", ondelete="CASCADE"), nullable=False, index=True
    )
    # 平文は保存しない（発行時に 1 度だけ返す）
    code_hash: Mapped[str] = mapped_column(sa.String(64), unique=True, nullable=False)
    role: Mapped[str] = mapped_column(FAMILY_ROLE, nullable=False)
    # role = child の招待では、親が先に作った参加者を指す
    target_membership_id: Mapped[int | None] = mapped_column(
        BigIntPk, sa.ForeignKey("family_memberships.id", ondelete="CASCADE"), nullable=True
    )
    expires_at = mapped_column(sa.DateTime(), nullable=False)
    used_at = mapped_column(sa.DateTime(), nullable=True)
    created_at = mapped_column(sa.DateTime(), nullable=False, default=utcnow)


__all__ = [
    "FAMILY_ROLE",
    "FamilyInvitationModel",
    "FamilyMembershipModel",
    "FamilyModel",
    "PointLedgerModel",
    "PointTransactionModel",
]
