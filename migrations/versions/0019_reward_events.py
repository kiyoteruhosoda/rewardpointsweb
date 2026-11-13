"""reward events (events and stickers)

"Effort cards" per child ledger (ADR-0042). The goal, the points earned on completion, and
the completion count go in ``reward_events``, and each sticker placed is one row in ``reward_event_stickers``.
Deleting a ledger deletes its events, and deleting an event deletes its stickers
(``ON DELETE CASCADE``).

Existing ledgers get no rows, so nothing looks different before and after this revision.

The definitions' source of truth is ``bounded_contexts/reward_points/infrastructure/reward_points_models.py``.

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
    # Indexes go away with the table. Dropping an index a foreign key uses first is rejected by MariaDB
    # (CLAUDE.md "DDL management")
    op.drop_table("reward_event_stickers")
    op.drop_table("reward_events")
