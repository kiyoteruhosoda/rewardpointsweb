"""silent round trip (画面を出さずに試した往復であることを控えに持たせる)

``sso_login_sessions`` に ``silent`` を足す（ADR-0052）。真なら ``prompt=none`` で
送り出した往復で、IdP が ``login_required`` などで戻しても失敗として扱わない。

⚠ **移行より前に始まった往復は偽になる。** それはボタンで始めた往復なので正しい。

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
