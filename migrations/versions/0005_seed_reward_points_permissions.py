"""seed reward points permissions

``member:*`` / ``point:*`` の権限コードと、ロールへの付与を投入する。値の正本は
``shared/domain/auth/master_data.py``（ここへ直書きしない）。投入処理は冪等なので、
既存の権限・ロール・初期管理者はそのまま残る。

Revision ID: seed_reward_points
Revises: reward_points
Create Date: 2026-07-30

"""

from __future__ import annotations

from alembic import op
from sqlalchemy.orm import Session

# revision identifiers, used by Alembic.
revision = "seed_reward_points"
down_revision = "reward_points"
branch_labels = None
depends_on = None

_ADDED_PERMISSION_CODES = ("member:view", "member:manage", "point:view", "point:manage")


def upgrade() -> None:
    from shared.infrastructure.master_data_seeder import seed_master_data

    session = Session(bind=op.get_bind())
    seed_master_data(session)
    session.flush()


def downgrade() -> None:
    from shared.infrastructure.models import Permission, role_permissions

    bind = op.get_bind()
    session = Session(bind=bind)
    permission_ids = [
        row_id for (row_id,) in session.query(Permission.id).filter(Permission.code.in_(_ADDED_PERMISSION_CODES)).all()
    ]
    if permission_ids:
        bind.execute(role_permissions.delete().where(role_permissions.c.permission_id.in_(permission_ids)))
    session.query(Permission).filter(Permission.code.in_(_ADDED_PERMISSION_CODES)).delete(synchronize_session=False)
    session.flush()
