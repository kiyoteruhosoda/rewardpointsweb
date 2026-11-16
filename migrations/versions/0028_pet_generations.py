"""pet generations: one row per pet raised on a ledger

The species is now chosen once per pet, and after the final stage the next pet starts from an
egg (ADR-0061, task #1046). ``pets`` (one row per ledger) becomes ``pet_generations`` (one row
per pet, ``UNIQUE (ledger_id, generation)``). Existing pets become generation 1, keeping the
day their egg was handed over.

The definitions' source of truth is ``bounded_contexts/reward_points/infrastructure/reward_points_models.py``.

Revision ID: pet_generations
Revises: pets
Create Date: 2026-11-16

"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision = "pet_generations"
down_revision = "pets"
branch_labels = None
depends_on = None

_BIGINT = sa.BigInteger().with_variant(sa.Integer(), "sqlite")
_SPECIES = sa.Enum("cat", "rabbit", "bird", "dragon", name="pet_species", native_enum=False)


def upgrade() -> None:
    op.create_table(
        "pet_generations",
        sa.Column("id", _BIGINT, primary_key=True, autoincrement=True),
        sa.Column("ledger_id", _BIGINT, nullable=False),
        sa.Column("generation", sa.Integer(), nullable=False),
        sa.Column("species", _SPECIES, nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["ledger_id"], ["point_ledgers.id"], ondelete="CASCADE"),
        sa.UniqueConstraint("ledger_id", "generation", name="uq_pet_generations_generation"),
        sa.CheckConstraint("generation >= 1", name="ck_pet_generations_generation_positive"),
    )
    op.execute(
        "INSERT INTO pet_generations (ledger_id, generation, species, created_at, updated_at) "
        "SELECT ledger_id, 1, species, created_at, updated_at FROM pets"
    )
    op.drop_table("pets")


def downgrade() -> None:
    op.create_table(
        "pets",
        sa.Column("id", _BIGINT, primary_key=True, autoincrement=True),
        sa.Column("ledger_id", _BIGINT, nullable=False),
        sa.Column("species", _SPECIES, nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["ledger_id"], ["point_ledgers.id"], ondelete="CASCADE"),
        sa.UniqueConstraint("ledger_id"),
    )
    # Keep the pet being raised now (the latest generation) on each ledger
    op.execute(
        "INSERT INTO pets (ledger_id, species, created_at, updated_at) "
        "SELECT g.ledger_id, g.species, g.created_at, g.updated_at FROM pet_generations g "
        "WHERE g.generation = (SELECT MAX(h.generation) FROM pet_generations h WHERE h.ledger_id = g.ledger_id)"
    )
    op.drop_table("pet_generations")
