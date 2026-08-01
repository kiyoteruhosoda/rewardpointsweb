"""guest independence proposal

親メンバーが子（ゲスト）の独立を指示し、子本人が承認する 2 段階の独立
（ADR-0014）のため、指示の状態を ``family_memberships`` に持つ。

定義の正本は ``bounded_contexts/reward_points/infrastructure/reward_points_models.py``。

Revision ID: membership_independence
Revises: family_point_ledger
Create Date: 2026-08-01

"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision = "membership_independence"
down_revision = "family_point_ledger"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("family_memberships") as batch:
        batch.add_column(sa.Column("independence_proposed_at", sa.DateTime(), nullable=True))


def downgrade() -> None:
    with op.batch_alter_table("family_memberships") as batch:
        batch.drop_column("independence_proposed_at")
