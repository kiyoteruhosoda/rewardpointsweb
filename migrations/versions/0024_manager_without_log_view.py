"""manager から log:view を外す (nolumiatask #786)

アプリのログは運用の記録で、manager の仕事には要らない。admin だけが見られるようにする。
シーダーは足すだけで外さないので、今ある環境からはここで外す。

Revision ID: manager_without_log_view
Revises: login_attempts
Create Date: 2026-10-30

"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision = "manager_without_log_view"
down_revision = "login_attempts"
branch_labels = None
depends_on = None

_PERMISSION = "log:view"

_roles = sa.table("roles", sa.column("id", sa.BigInteger), sa.column("name", sa.String))
_permissions = sa.table("permissions", sa.column("id", sa.BigInteger), sa.column("code", sa.String))
_role_permissions = sa.table(
    "role_permissions", sa.column("role_id", sa.BigInteger), sa.column("permission_id", sa.BigInteger)
)


def _ids(bind: sa.Connection) -> tuple[int, int] | None:
    role_id = bind.scalar(sa.select(_roles.c.id).where(_roles.c.id == 2))
    permission_id = bind.scalar(sa.select(_permissions.c.id).where(_permissions.c.code == _PERMISSION))
    return None if role_id is None or permission_id is None else (role_id, permission_id)


def upgrade() -> None:
    bind = op.get_bind()
    ids = _ids(bind)
    if ids is None:
        return
    bind.execute(
        _role_permissions.delete().where(
            _role_permissions.c.role_id == ids[0], _role_permissions.c.permission_id == ids[1]
        )
    )


def downgrade() -> None:
    bind = op.get_bind()
    ids = _ids(bind)
    if ids is None:
        return
    bind.execute(_role_permissions.insert().values(role_id=ids[0], permission_id=ids[1]))
