"""daily bonus

子の台帳ごとに「毎日いくつ足すか」を持たせる（ADR-0024）。台帳が消えれば設定も
消えるよう ``ON DELETE CASCADE`` にしてある（家族の解散・参加者の削除・独立の成立）。

``granted_through`` は渡し終えた最後の日。アプリが止まっていた日は、次に動いた
ときにここを起点にまとめて追いつく。既存の台帳には行が入らないので、
このリビジョンの前後で見え方は変わらない。

定義の正本は ``bounded_contexts/reward_points/infrastructure/reward_points_models.py``。

Revision ID: daily_bonus
Revises: point_transaction_correction
Create Date: 2026-08-09

"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision = "daily_bonus"
down_revision = "point_transaction_correction"
branch_labels = None
depends_on = None

_BIGINT = sa.BigInteger().with_variant(sa.Integer(), "sqlite")


def upgrade() -> None:
    op.create_table(
        "daily_bonuses",
        sa.Column("id", _BIGINT, primary_key=True, autoincrement=True),
        sa.Column("ledger_id", _BIGINT, nullable=False),
        sa.Column("amount", sa.Integer(), nullable=False),
        sa.Column("reason", sa.String(255), nullable=False),
        sa.Column("starts_on", sa.Date(), nullable=False),
        sa.Column("granted_through", sa.Date(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["ledger_id"], ["point_ledgers.id"], ondelete="CASCADE"),
        sa.UniqueConstraint("ledger_id", name="uq_daily_bonuses_ledger"),
        sa.CheckConstraint("amount > 0", name="ck_daily_bonuses_amount_positive"),
    )


def downgrade() -> None:
    # 索引は表と一緒に消える。外部キーが使う索引を先に落とすと MariaDB が拒む
    # （CLAUDE.md「DDL 管理」）
    op.drop_table("daily_bonuses")
