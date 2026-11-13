"""seed reward points permissions

Seeds the ``member:*`` / ``point:*`` permission codes and their grants to roles.

``member:*`` is later replaced by ``family:*`` in ADR-0009 (0007). This revision must seed
**the codes as of that revision**, so instead of the list in the source of truth
(``shared/domain/auth/master_data.py``) it uses this file's own
``_ADDED_PERMISSION_CODES``. The source of truth describes "how things should be now",
not how they were at past revisions.

Revision ID: seed_reward_points
Revises: reward_points
Create Date: 2026-07-30

"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.engine import Connection

# revision identifiers, used by Alembic.
revision = "seed_reward_points"
down_revision = "reward_points"
branch_labels = None
depends_on = None

_ADDED_PERMISSION_CODES = ("member:view", "member:manage", "point:view", "point:manage")
# Grants as of this revision (``manager`` gets everything, ``member`` gets read-only)
_GRANTS: dict[str, tuple[str, ...]] = {
    "admin": _ADDED_PERMISSION_CODES,
    "manager": _ADDED_PERMISSION_CODES,
    "member": ("member:view", "point:view"),
}

_roles = sa.table("roles", sa.column("id"), sa.column("name"))
_permissions = sa.table("permissions", sa.column("id"), sa.column("code"))
_role_permissions = sa.table("role_permissions", sa.column("role_id"), sa.column("permission_id"))


def _permission_id(bind: Connection, code: str) -> int:
    found = bind.scalar(sa.select(_permissions.c.id).where(_permissions.c.code == code))
    if found is None:
        bind.execute(_permissions.insert().values(code=code))
        found = bind.scalar(sa.select(_permissions.c.id).where(_permissions.c.code == code))
    return int(str(found))


def upgrade() -> None:
    bind = op.get_bind()
    permission_ids = {code: _permission_id(bind, code) for code in _ADDED_PERMISSION_CODES}
    for role_name, codes in _GRANTS.items():
        role_id = bind.scalar(sa.select(_roles.c.id).where(_roles.c.name == role_name))
        if role_id is None:
            continue
        for code in codes:
            exists = bind.scalar(
                sa.select(_role_permissions.c.role_id).where(
                    _role_permissions.c.role_id == role_id,
                    _role_permissions.c.permission_id == permission_ids[code],
                )
            )
            if exists is None:
                bind.execute(_role_permissions.insert().values(role_id=role_id, permission_id=permission_ids[code]))


def downgrade() -> None:
    bind = op.get_bind()
    ids = [
        row_id
        for (row_id,) in bind.execute(
            sa.select(_permissions.c.id).where(_permissions.c.code.in_(_ADDED_PERMISSION_CODES))
        ).all()
    ]
    if ids:
        bind.execute(_role_permissions.delete().where(_role_permissions.c.permission_id.in_(ids)))
    bind.execute(_permissions.delete().where(_permissions.c.code.in_(_ADDED_PERMISSION_CODES)))
