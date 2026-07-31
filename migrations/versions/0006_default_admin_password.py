"""default admin password

初期管理者の既定パスワードをメールアドレスと同じ文字列へ変更したことを、既存の
環境へも反映する。既定値のまま使われているアカウント（``password_hash`` が過去の
既定ハッシュと一致）だけを対象にし、運用者が自分で決めたパスワードには触れない。
値の正本は ``shared/domain/auth/master_data.py``（ここへ直書きしない）。

Revision ID: default_admin_password
Revises: seed_reward_points
Create Date: 2026-07-31

"""

from __future__ import annotations

import os

from alembic import op
from sqlalchemy.orm import Session

# revision identifiers, used by Alembic.
revision = "default_admin_password"
down_revision = "seed_reward_points"
branch_labels = None
depends_on = None


def upgrade() -> None:
    from shared.infrastructure.master_data_seeder import reconcile_default_admin

    session = Session(bind=op.get_bind())
    reconcile_default_admin(session, admin_password=os.environ.get("ADMIN_INITIAL_PASSWORD") or None)
    session.flush()


def downgrade() -> None:
    """既定値のままの管理者を、直前の既定ハッシュへ戻す。

    どのハッシュへ戻すかは ``SUPERSEDED_ADMIN_PASSWORD_HASHES`` の末尾（最も新しい
    旧既定値）を使う。ここでも、既定値以外のパスワードには触れない。
    """
    from shared.domain.auth import master_data
    from shared.infrastructure.models import User

    if not master_data.SUPERSEDED_ADMIN_PASSWORD_HASHES:
        return

    session = Session(bind=op.get_bind())
    admin = session.query(User).filter(User.email == master_data.DEFAULT_ADMIN_EMAIL).one_or_none()
    if admin is not None and admin.password_hash == master_data.DEFAULT_ADMIN_PASSWORD_HASH:
        admin.password_hash = master_data.SUPERSEDED_ADMIN_PASSWORD_HASHES[-1]
    session.flush()
