"""reward points (members / shares / point entries)

Adds the tables for members, shares, and point history. The definitions' source of truth is
``bounded_contexts/reward_points/infrastructure/reward_points_models.py``.

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
# Do not use DB-native ENUM (it becomes a VARCHAR with a CHECK constraint)
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
        # Keep the member even if the account is deleted (only the self-login link is removed)
        sa.ForeignKeyConstraint(["linked_user_id"], ["users.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
        # An account can see only one member as "my points"
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
        # Once the account it is shared with is gone, the share no longer means anything
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
        # Keep the history even if the recorder's account is deleted (history belongs to the member)
        sa.Column("recorded_by_user_id", _BIGINT, nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["member_id"], ["members.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["recorded_by_user_id"], ["users.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_point_entries_member_id"), "point_entries", ["member_id"])


def downgrade() -> None:
    # Do not drop the indexes; they go away with the tables (MariaDB cannot DROP an index on a
    # foreign key column on its own)
    op.drop_table("point_entries")
    op.drop_table("member_shares")
    op.drop_table("members")
