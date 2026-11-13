"""link round trip (record in the session that the round trip is for linking)

Adds ``link_user_id`` to ``sso_login_sessions`` (ADR-0036). When set, it is
**a round trip to link to a user already signed in**; when not set, it is a login round trip.

⚠ **No foreign key.** This table holds short-lived records and is not something to take
down with a deleted user (records of deleted users expire on their own).

⚠ **Round trips started before the migration become ``NULL``.** They are login round trips, so that is
correct - a round trip from before linking existed is always a login.

Revision ID: link_round_trip
Revises: password_is_optional
Create Date: 2026-09-14

"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision = "link_round_trip"
down_revision = "password_is_optional"
branch_labels = None
depends_on = None

_LINK_USER_ID = sa.Column(
    "link_user_id",
    sa.BigInteger().with_variant(sa.Integer(), "sqlite"),
    nullable=True,
)


def upgrade() -> None:
    op.add_column("sso_login_sessions", _LINK_USER_ID)


def downgrade() -> None:
    op.drop_column("sso_login_sessions", "link_user_id")
