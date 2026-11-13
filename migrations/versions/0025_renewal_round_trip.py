"""renewal round trip (record in the session that the round trip continues an expired login)

Adds ``renewal`` to ``sso_login_sessions`` (ADR-0058). When true, it is a "continue an expired login"
round trip started in an invisible frame, and the return goes to the result page with an exchange ticket (not back to the SPA screen).

⚠ **Round trips started before the migration become false.** They are login round trips, so that is correct.

Revision ID: renewal_round_trip
Revises: manager_without_log_view
Create Date: 2026-11-05

"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision = "renewal_round_trip"
down_revision = "manager_without_log_view"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "sso_login_sessions",
        sa.Column("renewal", sa.Boolean(), nullable=False, server_default=sa.false()),
    )


def downgrade() -> None:
    op.drop_column("sso_login_sessions", "renewal")
