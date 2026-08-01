"""password_reset_tokens.user_id を ON DELETE CASCADE にする

``password_reset_tokens.user_id`` → ``users.id`` の外部キーに ``ON DELETE`` が
無く、パスワード再設定を一度でも申請したアカウントの削除が本番（MariaDB）で
外部キーに阻まれて失敗していた。削除時に消してよいトークンなので、拒否では
なく追随（CASCADE）させる（docs/Progress.md T3）。

ベースライン（0001）はこの外部キーを無名で作っている。SQLite は無名の制約を
名前で落とせないため、``naming_convention`` を渡した batch モードで決め打ちの
名前を与えて落とす。MariaDB では実際に付いた名前（``…_ibfk_1`` 等）を
リフレクションで拾って使う。

Revision ID: password_reset_cascade
Revises: membership_independence
Create Date: 2026-08-01

"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision = "password_reset_cascade"
down_revision = "membership_independence"
branch_labels = None
depends_on = None

_TABLE = "password_reset_tokens"
_FK_NAME = "fk_password_reset_tokens_user_id_users"
_NAMING_CONVENTION = {"fk": "fk_%(table_name)s_%(column_0_name)s_%(referred_table_name)s"}


def _users_fk_name() -> str | None:
    inspector = sa.inspect(op.get_bind())
    for fk in inspector.get_foreign_keys(_TABLE):
        if fk["referred_table"] == "users":
            return fk["name"]
    return None


def _replace_users_fk(*, ondelete: str | None) -> None:
    current_name = _users_fk_name() or _FK_NAME
    with op.batch_alter_table(_TABLE, naming_convention=_NAMING_CONVENTION) as batch:
        batch.drop_constraint(current_name, type_="foreignkey")
        batch.create_foreign_key(_FK_NAME, "users", ["user_id"], ["id"], ondelete=ondelete)


def upgrade() -> None:
    _replace_users_fk(ondelete="CASCADE")


def downgrade() -> None:
    _replace_users_fk(ondelete=None)
