"""reward events (イベントとシール)

子の台帳ごとの「がんばりカード」（ADR-0042）。目標・達成でもらえるポイント・
達成回数を ``reward_events`` に、貼ったシールを 1 枚 1 行で ``reward_event_stickers``
に持つ。台帳が消えればイベントも、イベントが消えればシールも消える
（``ON DELETE CASCADE``）。

既存の台帳には行が入らないので、このリビジョンの前後で見え方は変わらない。

定義の正本は ``bounded_contexts/reward_points/infrastructure/reward_points_models.py``。

Revision ID: reward_events
Revises: link_round_trip
Create Date: 2026-10-03

"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision = "reward_events"
down_revision = "link_round_trip"
branch_labels = None
depends_on = None

_BIGINT = sa.BigInteger().with_variant(sa.Integer(), "sqlite")


def upgrade() -> None:
    op.create_table(
        "reward_events",
        sa.Column("id", _BIGINT, primary_key=True, autoincrement=True),
        sa.Column("ledger_id", _BIGINT, nullable=False),
        sa.Column("title", sa.String(100), nullable=False),
        sa.Column("reward_points", sa.Integer(), nullable=False),
        sa.Column("goal_count", sa.Integer(), nullable=False),
        sa.Column("completed_at", sa.DateTime(), nullable=True),
        sa.Column("awarded_transaction_id", _BIGINT, nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["ledger_id"], ["point_ledgers.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["awarded_transaction_id"], ["point_transactions.id"], ondelete="SET NULL"),
        sa.CheckConstraint("reward_points > 0", name="ck_reward_events_reward_positive"),
        sa.CheckConstraint("goal_count >= 1", name="ck_reward_events_goal_count_positive"),
    )
    op.create_index("ix_reward_events_ledger_id", "reward_events", ["ledger_id"])
    op.create_table(
        "reward_event_stickers",
        sa.Column("id", _BIGINT, primary_key=True, autoincrement=True),
        sa.Column("event_id", _BIGINT, nullable=False),
        sa.Column("number", sa.Integer(), nullable=False),
        sa.Column("stuck_at", sa.DateTime(), nullable=False),
        sa.Column("stuck_by_membership_id", _BIGINT, nullable=True),
        sa.ForeignKeyConstraint(["event_id"], ["reward_events.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["stuck_by_membership_id"], ["family_memberships.id"], ondelete="SET NULL"),
        sa.UniqueConstraint("event_id", "number", name="uq_reward_event_stickers_number"),
        sa.CheckConstraint("number >= 1", name="ck_reward_event_stickers_number_positive"),
    )


def downgrade() -> None:
    # 索引は表と一緒に消える。外部キーが使う索引を先に落とすと MariaDB が拒む
    # （CLAUDE.md「DDL 管理」）
    op.drop_table("reward_event_stickers")
    op.drop_table("reward_events")
