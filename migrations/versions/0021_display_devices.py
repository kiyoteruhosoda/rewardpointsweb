"""display devices (display device pairing)

Adds display devices (signage) through pairing (ADR-0047).

- Adds ``display`` as a position within a family. ``family_memberships.role`` and
  ``family_invitations.role`` are ``native_enum=False`` VARCHARs whose length is set by
  the longest value (``parent``, 6 characters). ``display`` is 7 characters, so widen them
- Adds tables for pairings (``display_pairings``) and device credentials (``display_credentials``)
- Adds the scope ``display:approve`` and the roles ``operator`` (operations administrator) and ``display`` (display device).
  ⚠ **admin does not get ``display:approve``** (admin does not look at household ledgers; ADR-0018)

Grants use constants this file holds (same approach as 0005 and 0010; master_data, the source of truth, is
"how things should be now", not the state at this revision). Roles are added by name without hard-coding ids
- in an environment where roles were created in the admin console, ids 5 and 6 may already be taken.

The definitions' source of truth is ``bounded_contexts/display_devices/infrastructure/display_devices_models.py``.

Revision ID: display_devices
Revises: reward_event_deadline
Create Date: 2026-10-05

"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.engine import Connection

# revision identifiers, used by Alembic.
revision = "display_devices"
down_revision = "reward_event_deadline"
branch_labels = None
depends_on = None

_BIGINT = sa.BigInteger().with_variant(sa.Integer(), "sqlite")
_ROLE_BEFORE = sa.Enum("owner", "parent", "child", name="family_role", native_enum=False)
_ROLE_AFTER = sa.Enum("owner", "parent", "child", "display", name="family_role", native_enum=False)
_ROLE_TABLES = ("family_memberships", "family_invitations")

_APPROVE = "display:approve"
# Roles added in this revision, and their scopes
_ADDED_ROLES: dict[str, tuple[str, ...]] = {
    "operator": ("dashboard:view", "gui:view", _APPROVE),
    "display": ("dashboard:view", "gui:view", "family:view", "point:view"),
}

_roles = sa.table("roles", sa.column("id"), sa.column("name"))
_permissions = sa.table("permissions", sa.column("id"), sa.column("code"))
_role_permissions = sa.table("role_permissions", sa.column("role_id"), sa.column("permission_id"))
_user_roles = sa.table("user_roles", sa.column("user_id"), sa.column("role_id"))
_memberships = sa.table("family_memberships", sa.column("role"))


def upgrade() -> None:
    for table in _ROLE_TABLES:
        with op.batch_alter_table(table) as batch:
            batch.alter_column("role", existing_type=_ROLE_BEFORE, type_=_ROLE_AFTER, existing_nullable=False)
    _create_tables()
    _seed_roles(op.get_bind())


def _create_tables() -> None:
    op.create_table(
        "display_pairings",
        sa.Column("id", _BIGINT, primary_key=True, autoincrement=True),
        sa.Column("user_code_hash", sa.String(64), nullable=False),
        sa.Column("device_code_hash", sa.String(64), nullable=False),
        sa.Column("expires_at", sa.DateTime(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("approved_account_id", _BIGINT, nullable=True),
        sa.Column("approved_at", sa.DateTime(), nullable=True),
        sa.Column("claimed_at", sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(["approved_account_id"], ["users.id"], ondelete="CASCADE"),
        sa.UniqueConstraint("user_code_hash"),
        sa.UniqueConstraint("device_code_hash"),
    )
    # Cleanup of expired rows runs every time a pairing starts. Add an index to look them up by expiry
    op.create_index("ix_display_pairings_expires_at", "display_pairings", ["expires_at"])
    op.create_index("ix_display_pairings_approved_account_id", "display_pairings", ["approved_account_id"])
    op.create_table(
        "display_credentials",
        sa.Column("account_id", _BIGINT, primary_key=True),
        sa.Column("credential_hash", sa.String(64), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("last_used_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["account_id"], ["users.id"], ondelete="CASCADE"),
        sa.UniqueConstraint("credential_hash"),
    )


def _role_id(bind: Connection, name: str) -> int | None:
    found = bind.scalar(sa.select(_roles.c.id).where(_roles.c.name == name))
    return None if found is None else int(str(found))


def _permission_id(bind: Connection, code: str) -> int | None:
    found = bind.scalar(sa.select(_permissions.c.id).where(_permissions.c.code == code))
    return None if found is None else int(str(found))


def _seed_roles(bind: Connection) -> None:
    if _permission_id(bind, _APPROVE) is None:
        bind.execute(_permissions.insert().values(code=_APPROVE))
    for role_name, codes in _ADDED_ROLES.items():
        role_id = _role_id(bind, role_name)
        if role_id is None:
            bind.execute(_roles.insert().values(name=role_name))
            role_id = _role_id(bind, role_name)
        for code in codes:
            permission_id = _permission_id(bind, code)
            if role_id is None or permission_id is None:
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
    # The reverted column cannot hold ``display``. Remove display device memberships first
    # (the accounts remain without the role; they can be deleted from the admin console)
    bind.execute(_memberships.delete().where(_memberships.c.role == "display"))
    _drop_roles(bind)
    op.drop_table("display_credentials")
    op.drop_table("display_pairings")
    for table in _ROLE_TABLES:
        with op.batch_alter_table(table) as batch:
            batch.alter_column("role", existing_type=_ROLE_AFTER, type_=_ROLE_BEFORE, existing_nullable=False)


def _drop_roles(bind: Connection) -> None:
    for role_name in _ADDED_ROLES:
        role_id = _role_id(bind, role_name)
        if role_id is None:
            continue
        bind.execute(_user_roles.delete().where(_user_roles.c.role_id == role_id))
        bind.execute(_role_permissions.delete().where(_role_permissions.c.role_id == role_id))
        bind.execute(_roles.delete().where(_roles.c.id == role_id))
    permission_id = _permission_id(bind, _APPROVE)
    if permission_id is not None:
        bind.execute(_role_permissions.delete().where(_role_permissions.c.permission_id == permission_id))
        bind.execute(_permissions.delete().where(_permissions.c.id == permission_id))
