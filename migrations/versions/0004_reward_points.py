"""reward points (members / shares / point entries)

メンバー・共有・ポイント履歴のテーブルを追加する。定義の正本は
``bounded_contexts/reward_points/infrastructure/reward_points_models.py``。

Revision ID: reward_points
Revises: account_security
Create Date: 2026-07-30

"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision = "reward_points"
down_revision = "account_security"
branch_labels = None
depends_on = None

_BIGINT = sa.BigInteger().with_variant(sa.Integer(), "sqlite")
# DB ネイティブ ENUM は使わない（CHECK 制約付き VARCHAR になる）
_POINT_ENTRY_TYPE = sa.Enum("addition", "consumption", name="point_entry_type", native_enum=False)
_MEMBER_ACCESS_LEVEL = sa.Enum("view", "manage", name="member_access_level", native_enum=False)


def upgrade() -> None:
    op.create_table(
        "members",
        sa.Column("id", _BIGINT, autoincrement=True, nullable=False),
        sa.Column("name", sa.String(length=100), nullable=False),
        sa.Column("owner_user_id", _BIGINT, nullable=False),
        sa.Column("linked_user_id", _BIGINT, nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["owner_user_id"], ["users.id"]),
        # アカウントが消えてもメンバーは残す（本人ログインの紐付けだけが外れる）
        sa.ForeignKeyConstraint(["linked_user_id"], ["users.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
        # 1 つのアカウントが「自分のポイント」として見られるメンバーは 1 人だけ
        sa.UniqueConstraint("linked_user_id"),
    )
    op.create_index(op.f("ix_members_owner_user_id"), "members", ["owner_user_id"])

    op.create_table(
        "member_shares",
        sa.Column("member_id", _BIGINT, nullable=False),
        sa.Column("user_id", _BIGINT, nullable=False),
        sa.Column("access_level", _MEMBER_ACCESS_LEVEL, nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["member_id"], ["members.id"], ondelete="CASCADE"),
        # 共有先のアカウントが消えれば、その共有はもう意味を持たない
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("member_id", "user_id"),
    )

    op.create_table(
        "point_entries",
        sa.Column("id", _BIGINT, autoincrement=True, nullable=False),
        sa.Column("member_id", _BIGINT, nullable=False),
        sa.Column("entry_type", _POINT_ENTRY_TYPE, nullable=False),
        sa.Column("occurred_at", sa.DateTime(), nullable=False),
        sa.Column("points", sa.Integer(), nullable=False),
        sa.Column("reason", sa.String(length=255), nullable=True),
        sa.Column("application", sa.String(length=255), nullable=True),
        # 記録者のアカウントが消えても履歴は残す（履歴はメンバーのもの）
        sa.Column("recorded_by_user_id", _BIGINT, nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["member_id"], ["members.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["recorded_by_user_id"], ["users.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_point_entries_member_id"), "point_entries", ["member_id"])


def downgrade() -> None:
    op.drop_index(op.f("ix_point_entries_member_id"), table_name="point_entries")
    op.drop_table("point_entries")
    op.drop_table("member_shares")
    op.drop_index(op.f("ix_members_owner_user_id"), table_name="members")
    op.drop_table("members")
