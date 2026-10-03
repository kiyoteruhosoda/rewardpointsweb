"""reward event deadline (イベントの期限)

``reward_events`` に任意の期限（日付）を足す（ADR-0043）。既存のイベントは
``NULL``（期限なし）になり、これまでどおりいつまでも貼れる。

定義の正本は ``bounded_contexts/reward_points/infrastructure/reward_points_models.py``。

Revision ID: reward_event_deadline
Revises: reward_events
Create Date: 2026-10-03

"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision = "reward_event_deadline"
down_revision = "reward_events"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("reward_events", sa.Column("deadline", sa.Date(), nullable=True))


def downgrade() -> None:
    op.drop_column("reward_events", "deadline")
