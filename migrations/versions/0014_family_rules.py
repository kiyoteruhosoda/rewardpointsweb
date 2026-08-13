"""family rules

家族で決めた約束ごとのメモを ``families`` に持たせる（ADR-0027）。子ども一人ひとり
ではなく家族に 1 つで、参加している全員が同じ文面を読む。

既存の家族には NULL が入る（＝まだ書いていない）。書いていない状態と空文字を
区別するため、既定値は置かない。

定義の正本は ``bounded_contexts/reward_points/infrastructure/reward_points_models.py``。

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
