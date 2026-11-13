"""point transaction correction

Makes corrections to a record (a reversal plus a rewrite with the correct content) traceable on the ledger
(ADR-0022). Adds ``corrects_id``, a reference from the corrected row to the original row.

All existing rows get NULL (no row has been created by a correction yet), so
nothing looks different before and after this revision.

``ON DELETE SET NULL`` is used so that when a ledger is deleted wholesale because independence takes effect
(ADR-0014), deleting either the original row or the corrected row first is not rejected.

The definitions' source of truth is ``bounded_contexts/reward_points/infrastructure/reward_points_models.py``.

Revision ID: point_transaction_correction
Revises: membership_display_order
Create Date: 2026-08-02

"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision = "point_transaction_correction"
down_revision = "membership_display_order"
branch_labels = None
depends_on = None

_BIGINT = sa.BigInteger().with_variant(sa.Integer(), "sqlite")


def upgrade() -> None:
    with op.batch_alter_table("point_transactions") as batch:
        batch.add_column(sa.Column("corrects_id", _BIGINT, nullable=True))
        batch.create_unique_constraint("uq_point_transactions_corrects", ["corrects_id"])
        batch.create_foreign_key(
            "fk_point_transactions_corrects",
            "point_transactions",
            ["corrects_id"],
            ["id"],
            ondelete="SET NULL",
        )


def downgrade() -> None:
    with op.batch_alter_table("point_transactions") as batch:
        batch.drop_constraint("fk_point_transactions_corrects", type_="foreignkey")
        batch.drop_constraint("uq_point_transactions_corrects", type_="unique")
        batch.drop_column("corrects_id")
