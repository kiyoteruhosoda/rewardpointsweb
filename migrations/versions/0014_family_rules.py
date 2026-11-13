"""family rules

Gives ``families`` a memo of the rules the family agreed on (ADR-0027). There is one per family,
not one per child, and every participant reads the same text.

Existing families get NULL (= not written yet). No default is set, so that "not written"
can be told apart from an empty string.

The definitions' source of truth is ``bounded_contexts/reward_points/infrastructure/reward_points_models.py``.

Revision ID: family_rules
Revises: daily_bonus
Create Date: 2026-08-12

"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision = "family_rules"
down_revision = "daily_bonus"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("families", sa.Column("rules", sa.Text(), nullable=True))


def downgrade() -> None:
    op.drop_column("families", "rules")
