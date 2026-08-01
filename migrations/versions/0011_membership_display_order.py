"""membership display order

家族が参加者の並び順を決められるようにする。ナビゲーションとダッシュボードは
この順で子を並べる。

既存の行はすべて 0 で入り、同じ値のあいだは ID 順（＝作られた順）に落ちるので、
このリビジョンの前後で見え方は変わらない。

定義の正本は ``bounded_contexts/reward_points/infrastructure/reward_points_models.py``。

Revision ID: membership_display_order
Revises: realign_roles
Create Date: 2026-08-02

"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision = "membership_display_order"
down_revision = "realign_roles"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("family_memberships") as batch:
        batch.add_column(sa.Column("display_order", sa.Integer(), nullable=False, server_default="0"))


def downgrade() -> None:
    with op.batch_alter_table("family_memberships") as batch:
        batch.drop_column("display_order")
