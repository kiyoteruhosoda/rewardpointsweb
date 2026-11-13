"""seed master data

Seeds roles, permissions, and the initial administrator. The source of truth for the values is
``shared/domain/auth/master_data.py`` (do not hard-code them here).

Writes go through **Core table definitions that mirror the schema at this point**, not the
ORM models. The models change in later migrations (ADR-0011 added ``username`` /
``display_name`` to ``users``), so writing through the models would fail while applying
past revisions, because they would reference columns that do not exist yet.

Revision ID: seed_master_data
Revises: init_master
Create Date: 2026-07-17

"""

from __future__ import annotations

import os
from datetime import UTC, datetime

import sqlalchemy as sa
from alembic import op
from sqlalchemy.engine import Connection

# revision identifiers, used by Alembic.
revision = "seed_master_data"
down_revision = "init_master"
branch_labels = None
depends_on = None

# Write only the columns that exist at this revision (columns added later use their defaults)
_roles = sa.table("roles", sa.column("id"), sa.column("name"))
_permissions = sa.table("permissions", sa.column("id"), sa.column("code"))
_role_permissions = sa.table("role_permissions", sa.column("role_id"), sa.column("permission_id"))
_user_roles = sa.table("user_roles", sa.column("user_id"), sa.column("role_id"))
_users = sa.table(
    "users",
    sa.column("id"),
    sa.column("email"),
    sa.column("username"),
    sa.column("password_hash"),
    sa.column("is_active"),
    sa.column("created_at"),
    sa.column("updated_at"),
)


def _seed_roles(bind: Connection) -> dict[str, int]:
    from shared.domain.auth import master_data

    ids: dict[str, int] = {}
    for role_id, name in master_data.ROLES:
        found = bind.scalar(sa.select(_roles.c.id).where(_roles.c.name == name))
        if found is None:
            bind.execute(_roles.insert().values(id=role_id, name=name))
            found = role_id
        ids[name] = found
    return ids


def _seed_permissions(bind: Connection) -> dict[str, int]:
    from shared.domain.auth import master_data

    ids: dict[str, int] = {}
    for code in master_data.PERMISSION_CODES:
        found = bind.scalar(sa.select(_permissions.c.id).where(_permissions.c.code == code))
        if found is None:
            bind.execute(_permissions.insert().values(code=code))
            found = bind.scalar(sa.select(_permissions.c.id).where(_permissions.c.code == code))
        ids[code] = int(str(found))
    return ids


def _grant(bind: Connection, roles: dict[str, int], permissions: dict[str, int]) -> None:
    from shared.domain.auth import master_data

    for role_name, codes in master_data.ROLE_PERMISSIONS.items():
        role_id = roles[role_name]
        for code in codes:
            permission_id = permissions[code]
            exists = bind.scalar(
                sa.select(_role_permissions.c.role_id).where(
                    _role_permissions.c.role_id == role_id,
                    _role_permissions.c.permission_id == permission_id,
                )
            )
            if exists is None:
                bind.execute(_role_permissions.insert().values(role_id=role_id, permission_id=permission_id))


def _seed_admin(bind: Connection, roles: dict[str, int]) -> None:
    from shared.domain.auth import master_data

    if bind.scalar(sa.select(_users.c.id).where(_users.c.email == master_data.DEFAULT_ADMIN_EMAIL)) is not None:
        return

    from werkzeug.security import generate_password_hash

    plain = os.environ.get("ADMIN_INITIAL_PASSWORD") or None
    now = datetime.now(UTC).replace(tzinfo=None)  # Contract: stored values are naive UTC
    bind.execute(
        _users.insert().values(
            id=master_data.DEFAULT_ADMIN_ID,
            email=master_data.DEFAULT_ADMIN_EMAIL,
            # At this revision ``username`` is the display name (it becomes the identifier from ADR-0011 on)
            username=master_data.DEFAULT_ADMIN_DISPLAY_NAME,
            password_hash=generate_password_hash(plain) if plain else master_data.DEFAULT_ADMIN_PASSWORD_HASH,
            is_active=True,
            created_at=now,
            updated_at=now,
        )
    )
    role_id = roles.get(master_data.DEFAULT_ADMIN_ROLE)
    if role_id is not None:
        bind.execute(_user_roles.insert().values(user_id=master_data.DEFAULT_ADMIN_ID, role_id=role_id))


def upgrade() -> None:
    bind = op.get_bind()
    roles = _seed_roles(bind)
    permissions = _seed_permissions(bind)
    _grant(bind, roles, permissions)
    _seed_admin(bind, roles)


def downgrade() -> None:
    from shared.domain.auth import master_data

    bind = op.get_bind()
    bind.execute(_role_permissions.delete())
    bind.execute(_user_roles.delete())
    bind.execute(_users.delete().where(_users.c.email == master_data.DEFAULT_ADMIN_EMAIL))
    bind.execute(_permissions.delete().where(_permissions.c.code.in_(master_data.PERMISSION_CODES)))
    bind.execute(_roles.delete().where(_roles.c.name.in_([name for _, name in master_data.ROLES])))
