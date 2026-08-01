"""seed reward points permissions

``member:*`` / ``point:*`` の権限コードと、ロールへの付与を投入する。

``member:*`` はこの後 ADR-0009 で ``family:*`` へ置き換わる（0007）。ここでは
**そのリビジョン時点のコード** を投入する必要があるため、正本
（``shared/domain/auth/master_data.py``）の一覧ではなく、このファイルが持つ
``_ADDED_PERMISSION_CODES`` を使う。正本は「今あるべき姿」を表すもので、
過去のリビジョンの姿ではない。

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
# このリビジョン時点の付与（``manager`` は全て、``member`` は閲覧のみ）
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
