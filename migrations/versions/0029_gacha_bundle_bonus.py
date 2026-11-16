"""gacha draws: mark the free draw of a bundle

Ten draws at once come with one free draw (task #1047). ``gacha_draws.is_bonus`` marks it;
it has no ledger row. Existing draws are all paid single draws (``false``).

The definitions' source of truth is ``bounded_contexts/reward_points/infrastructure/reward_points_models.py``.

Revision ID: gacha_bundle_bonus
Revises: pet_generations
Create Date: 2026-11-16

"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision = "gacha_bundle_bonus"
down_revision = "pet_generations"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("gacha_draws", sa.Column("is_bonus", sa.Boolean(), nullable=False, server_default=sa.false()))


def downgrade() -> None:
    with op.batch_alter_table("gacha_draws") as batch:
        batch.drop_column("is_bonus")
