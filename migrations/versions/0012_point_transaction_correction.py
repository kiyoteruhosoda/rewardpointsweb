"""point transaction correction

記録の訂正（打ち消し ＋ 正しい内容の書き直し）を台帳の上で追えるようにする
（ADR-0022）。訂正後の行から元の行への参照 ``corrects_id`` を足す。

既存の行はすべて NULL で入る（訂正されて生まれた行がまだ無いため）ので、
このリビジョンの前後で見え方は変わらない。

``ON DELETE SET NULL`` にしてあるのは、独立の成立で台帳ごと消すとき
（ADR-0014）に、元の行と訂正後の行のどちらを先に消しても拒まれないようにするため。

定義の正本は ``bounded_contexts/reward_points/infrastructure/reward_points_models.py``。

Revision ID: point_transaction_correction
Revises: membership_display_order
Create Date: 2026-08-02

"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision = "point_transaction_correction"
down_revision = "membership_display_order"
branch_labels = None
depends_on = None

_BIGINT = sa.BigInteger().with_variant(sa.Integer(), "sqlite")


def upgrade() -> None:
    with op.batch_alter_table("point_transactions") as batch:
        batch.add_column(sa.Column("corrects_id", _BIGINT, nullable=True))
        batch.create_unique_constraint("uq_point_transactions_corrects", ["corrects_id"])
        batch.create_foreign_key(
            "fk_point_transactions_corrects",
            "point_transactions",
            ["corrects_id"],
            ["id"],
            ondelete="SET NULL",
        )


def downgrade() -> None:
    with op.batch_alter_table("point_transactions") as batch:
        batch.drop_constraint("fk_point_transactions_corrects", type_="foreignkey")
        batch.drop_constraint("uq_point_transactions_corrects", type_="unique")
        batch.drop_column("corrects_id")
