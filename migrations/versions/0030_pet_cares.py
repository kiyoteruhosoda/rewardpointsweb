"""pet cares and the pet:care scope

The child and the parents can care for a hatched pet (ADR-0061, task #1128). Each recorded care
is one row of ``pet_cares``, hung off the pet (``pet_generations``). Care is free and does not
touch growth; the mood and the friendship are worked out from these rows.

Also adds the ``pet:care`` permission and grants it to ``member`` (parents) and ``guest``
(children). Which ledger is decided by the role within the family, like ``pet:choose``.

The definitions' source of truth is ``bounded_contexts/reward_points/infrastructure/reward_points_models.py``.

Revision ID: pet_cares
Revises: gacha_bundle_bonus
Create Date: 2026-11-23

"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.engine import Connection

# revision identifiers, used by Alembic.
revision = "pet_cares"
down_revision = "gacha_bundle_bonus"
branch_labels = None
depends_on = None

_BIGINT = sa.BigInteger().with_variant(sa.Integer(), "sqlite")
_KIND = sa.Enum("feed", "pat", "play", "bath", name="pet_care_kind", native_enum=False)

_PERMISSION = "pet:care"
_GRANTED_ROLES = ("member", "guest")

_roles = sa.table("roles", sa.column("id"), sa.column("name"))
_permissions = sa.table("permissions", sa.column("id"), sa.column("code"))
_role_permissions = sa.table("role_permissions", sa.column("role_id"), sa.column("permission_id"))


def upgrade() -> None:
    op.create_table(
        "pet_cares",
        sa.Column("id", _BIGINT, primary_key=True, autoincrement=True),
        sa.Column("pet_id", _BIGINT, nullable=False),
        sa.Column("kind", _KIND, nullable=False),
        sa.Column("cared_at", sa.DateTime(), nullable=False),
        sa.Column("care_day", sa.Date(), nullable=False),
        sa.Column("cared_by_membership_id", _BIGINT, nullable=True),
        sa.ForeignKeyConstraint(["pet_id"], ["pet_generations.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["cared_by_membership_id"], ["family_memberships.id"], ondelete="SET NULL"),
    )
    op.create_index("ix_pet_cares_pet_cared", "pet_cares", ["pet_id", "cared_at"])
    _grant_care_permission(op.get_bind())


def _grant_care_permission(bind: Connection) -> None:
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
    op.drop_table("pet_cares")
