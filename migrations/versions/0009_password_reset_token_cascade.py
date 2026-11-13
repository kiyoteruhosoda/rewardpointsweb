"""Make password_reset_tokens.user_id ON DELETE CASCADE

The ``password_reset_tokens.user_id`` -> ``users.id`` foreign key had no ``ON DELETE``, so in
production (MariaDB) deleting any account that had ever requested a password reset
failed on the foreign key. The tokens may be deleted along with the account, so make it
follow (CASCADE) rather than reject (docs/Progress.md T3).

The baseline (0001) creates this foreign key without a name. SQLite cannot drop an unnamed
constraint by name, so batch mode with a ``naming_convention`` gives it a fixed name
to drop it by. On MariaDB the actual name (``…_ibfk_1`` etc.) is picked up
by reflection and used.

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
