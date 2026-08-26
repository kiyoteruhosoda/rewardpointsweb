"""seed master data

ロール・権限・初期管理者を投入する。値の正本は
``shared/domain/auth/master_data.py``（ここへ直書きしない）。

書き込みは ORM モデルではなく **この時点のスキーマを写した Core のテーブル定義**
で行う。モデルは後のマイグレーションで変わる（ADR-0011 で ``users`` に
``username`` / ``display_name`` が入った）ため、モデル経由で書くと、過去の
リビジョンを適用する途中でまだ存在しない列を参照して落ちる。

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

# このリビジョン時点の列だけを書く（後から増えた列は既定値に任せる）
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
    now = datetime.now(UTC).replace(tzinfo=None)  # 契約: 保存値は naive な UTC
    bind.execute(
        _users.insert().values(
            id=master_data.DEFAULT_ADMIN_ID,
            email=master_data.DEFAULT_ADMIN_EMAIL,
            # このリビジョンの ``username`` は表示名（識別子になるのは ADR-0011 以降）
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
