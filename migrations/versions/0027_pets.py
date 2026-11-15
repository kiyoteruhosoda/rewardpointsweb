"""pets (species per child ledger) and the pet:choose scope

The pet on a child ledger (ADR-0061). Only the chosen species is stored; growth comes from
the ledger. No row means "an egg, not chosen yet", so existing ledgers need no rows. The row
goes with the ledger (``ON DELETE CASCADE``).

Also adds the ``pet:choose`` permission and grants it to ``member`` (parents) and ``guest``
(children). The codes are this file's own constants, not the source of truth in
``shared/domain/auth/master_data.py`` (that file describes "now", not this revision).

The definitions' source of truth is ``bounded_contexts/reward_points/infrastructure/reward_points_models.py``.

Revision ID: pets
Revises: gachas
Create Date: 2026-11-15

"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.engine import Connection

# revision identifiers, used by Alembic.
revision = "pets"
down_revision = "gachas"
branch_labels = None
depends_on = None

_BIGINT = sa.BigInteger().with_variant(sa.Integer(), "sqlite")
_SPECIES = sa.Enum("cat", "rabbit", "bird", "dragon", name="pet_species", native_enum=False)

_PERMISSION = "pet:choose"
_GRANTED_ROLES = ("member", "guest")

_roles = sa.table("roles", sa.column("id"), sa.column("name"))
_permissions = sa.table("permissions", sa.column("id"), sa.column("code"))
_role_permissions = sa.table("role_permissions", sa.column("role_id"), sa.column("permission_id"))


def upgrade() -> None:
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
    _grant_choose_permission(op.get_bind())


def _grant_choose_permission(bind: Connection) -> None:
    permission_id = bind.scalar(sa.select(_permissions.c.id).where(_permissions.c.code == _PERMISSION))
    if permission_id is None:
        bind.execute(_permissions.insert().values(code=_PERMISSION))
        permission_id = bind.scalar(sa.select(_permissions.c.id).where(_permissions.c.code == _PERMISSION))
    for role_name in _GRANTED_ROLES:
        role_id = bind.scalar(sa.select(_roles.c.id).where(_roles.c.name == role_name))
        if role_id is None:
            continue
        granted = bind.scalar(
            sa.select(_role_permissions.c.role_id).where(
                _role_permissions.c.role_id == role_id, _role_permissions.c.permission_id == permission_id
            )
        )
        if granted is None:
            bind.execute(_role_permissions.insert().values(role_id=role_id, permission_id=permission_id))


def downgrade() -> None:
    bind = op.get_bind()
    permission_id = bind.scalar(sa.select(_permissions.c.id).where(_permissions.c.code == _PERMISSION))
    if permission_id is not None:
        bind.execute(_role_permissions.delete().where(_role_permissions.c.permission_id == permission_id))
        bind.execute(_permissions.delete().where(_permissions.c.id == permission_id))
    op.drop_table("pets")
