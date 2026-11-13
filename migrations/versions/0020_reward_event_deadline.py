"""reward event deadline (event deadlines)

Adds an optional deadline (date) to ``reward_events`` (ADR-0043). Existing events become
``NULL`` (no deadline), and stickers can still be placed on them indefinitely, as before.

The definitions' source of truth is ``bounded_contexts/reward_points/infrastructure/reward_points_models.py``.

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
