"""default admin password

Applies to existing environments the change of the initial administrator's default password
to the same string as the email address. Only accounts still using the default (whose
``password_hash`` matches a past default hash) are targeted; passwords operators chose are left alone.
The source of truth for the values is ``shared/domain/auth/master_data.py`` (do not hard-code them here).

At this revision the ``users`` identifier is still the email address, so the target is
looked up by ``email`` (``username`` becomes the identifier from 0007 on).

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

    # Move only accounts still on the default value to the new default
    op.get_bind().execute(
        _users.update()
        .where(
            _users.c.email == master_data.DEFAULT_ADMIN_EMAIL,
            _users.c.password_hash.in_(list(master_data.SUPERSEDED_ADMIN_PASSWORD_HASHES)),
        )
        .values(password_hash=target_hash)
    )


def downgrade() -> None:
    """Revert administrators still on the default to the previous default hash.

    The hash to revert to is the last entry of ``SUPERSEDED_ADMIN_PASSWORD_HASHES`` (the newest
    old default). Here too, passwords other than the default are left alone.
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
