"""default admin password

初期管理者の既定パスワードをメールアドレスと同じ文字列へ変更したことを、既存の
環境へも反映する。既定値のまま使われているアカウント（``password_hash`` が過去の
既定ハッシュと一致）だけを対象にし、運用者が自分で決めたパスワードには触れない。
値の正本は ``shared/domain/auth/master_data.py``（ここへ直書きしない）。

このリビジョン時点では ``users`` の識別子はまだメールアドレスなので、対象は
``email`` で引く（``username`` が識別子になるのは 0007 以降）。

Revision ID: default_admin_password
Revises: seed_reward_points
Create Date: 2026-07-31

"""

from __future__ import annotations

import os

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision = "default_admin_password"
down_revision = "seed_reward_points"
branch_labels = None
depends_on = None

_users = sa.table("users", sa.column("id"), sa.column("email"), sa.column("password_hash"))


def upgrade() -> None:
    from shared.domain.auth import master_data

    plain = os.environ.get("ADMIN_INITIAL_PASSWORD") or None
    if plain:
        from werkzeug.security import generate_password_hash

        target_hash = generate_password_hash(plain)
    else:
        target_hash = master_data.DEFAULT_ADMIN_PASSWORD_HASH

    # 既定値のまま使われているアカウントだけを新しい既定値へ追随させる
    op.get_bind().execute(
        _users.update()
        .where(
            _users.c.email == master_data.DEFAULT_ADMIN_EMAIL,
            _users.c.password_hash.in_(list(master_data.SUPERSEDED_ADMIN_PASSWORD_HASHES)),
        )
        .values(password_hash=target_hash)
    )


def downgrade() -> None:
    """既定値のままの管理者を、直前の既定ハッシュへ戻す。

    どのハッシュへ戻すかは ``SUPERSEDED_ADMIN_PASSWORD_HASHES`` の末尾（最も新しい
    旧既定値）を使う。ここでも、既定値以外のパスワードには触れない。
    """
    from shared.domain.auth import master_data

    if not master_data.SUPERSEDED_ADMIN_PASSWORD_HASHES:
        return

    op.get_bind().execute(
        _users.update()
        .where(
            _users.c.email == master_data.DEFAULT_ADMIN_EMAIL,
            _users.c.password_hash == master_data.DEFAULT_ADMIN_PASSWORD_HASH,
        )
        .values(password_hash=master_data.SUPERSEDED_ADMIN_PASSWORD_HASHES[-1])
    )
