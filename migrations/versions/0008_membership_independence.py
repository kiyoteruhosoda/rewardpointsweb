"""guest independence proposal

Stores the proposal state in ``family_memberships`` for the two-step independence (ADR-0014),
in which a parent member proposes that a child (guest) become independent and the child approves it.

The definitions' source of truth is ``bounded_contexts/reward_points/infrastructure/reward_points_models.py``.

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
