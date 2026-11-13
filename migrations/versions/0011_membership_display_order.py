"""membership display order

Lets a family decide the order of its participants. Navigation and the dashboard
list children in this order.

All existing rows get 0, and ties fall back to ID order (= creation order), so
nothing looks different before and after this revision.

The definitions' source of truth is ``bounded_contexts/reward_points/infrastructure/reward_points_models.py``.

Revision ID: membership_display_order
Revises: realign_roles
Create Date: 2026-08-02

"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision = "membership_display_order"
down_revision = "realign_roles"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("family_memberships") as batch:
        batch.add_column(sa.Column("display_order", sa.Integer(), nullable=False, server_default="0"))


def downgrade() -> None:
    with op.batch_alter_table("family_memberships") as batch:
        batch.drop_column("display_order")
