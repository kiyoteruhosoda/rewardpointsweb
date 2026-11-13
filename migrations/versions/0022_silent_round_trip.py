"""silent round trip (record in the session that the round trip was tried without showing a screen)

Adds ``silent`` to ``sso_login_sessions`` (ADR-0052). When true, the round trip was sent with
``prompt=none``, and an IdP response such as ``login_required`` is not treated as a failure.

⚠ **Round trips started before the migration become false.** They were started by a button, so that is correct.

Revision ID: silent_round_trip
Revises: display_devices
Create Date: 2026-10-22

"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision = "silent_round_trip"
down_revision = "display_devices"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "sso_login_sessions",
        sa.Column("silent", sa.Boolean(), nullable=False, server_default=sa.false()),
    )


def downgrade() -> None:
    op.drop_column("sso_login_sessions", "silent")
