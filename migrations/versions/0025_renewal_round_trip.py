"""renewal round trip (切れたログインを続ける往復であることを控えに持たせる)

``sso_login_sessions`` に ``renewal`` を足す（ADR-0058）。真なら、画面が見えない枠で始めた
「切れたログインを続ける」往復で、戻りは引き換え券を付けて結果の頁へ送る（SPA の画面へは戻さない）。

⚠ **移行より前に始まった往復は偽になる。** それはログインの往復なので正しい。

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
