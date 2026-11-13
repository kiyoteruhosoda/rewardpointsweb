"""daily bonus

Gives each child's ledger a "how many to add every day" setting (ADR-0024). It is ``ON DELETE CASCADE``
so the setting goes away with the ledger (family dissolved, participant deleted, independence taken effect).

``granted_through`` is the last day already granted. Days on which the app was down are caught up
in one go from here the next time it runs. Existing ledgers get no row, so
nothing looks different before and after this revision.

The definitions' source of truth is ``bounded_contexts/reward_points/infrastructure/reward_points_models.py``.

Revision ID: daily_bonus
Revises: point_transaction_correction
Create Date: 2026-08-09

"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision = "daily_bonus"
down_revision = "point_transaction_correction"
branch_labels = None
depends_on = None

_BIGINT = sa.BigInteger().with_variant(sa.Integer(), "sqlite")


def upgrade() -> None:
    op.create_table(
        "daily_bonuses",
        sa.Column("id", _BIGINT, primary_key=True, autoincrement=True),
        sa.Column("ledger_id", _BIGINT, nullable=False),
        sa.Column("amount", sa.Integer(), nullable=False),
        sa.Column("reason", sa.String(255), nullable=False),
        sa.Column("starts_on", sa.Date(), nullable=False),
        sa.Column("granted_through", sa.Date(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["ledger_id"], ["point_ledgers.id"], ondelete="CASCADE"),
        sa.UniqueConstraint("ledger_id", name="uq_daily_bonuses_ledger"),
        sa.CheckConstraint("amount > 0", name="ck_daily_bonuses_amount_positive"),
    )


def downgrade() -> None:
    # Indexes go away with the table. Dropping an index a foreign key uses first is rejected by MariaDB
    # (CLAUDE.md "DDL management")
    op.drop_table("daily_bonuses")
