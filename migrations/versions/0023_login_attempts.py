"""login attempts

宛名ごとの失敗の控え（ADR-0055）。プロセスのメモリではなく DB に置くのは、
Gunicorn が複数ワーカーで動くため（ワーカーの数だけ試せてしまう）。

主キーは（用途, 宛名）。宛名は**送られてきたユーザー名**で、実在する
アカウントとは結ばない（実在するものだけを数えると、断られるかどうかで
存在が分かってしまう）。期限切れの行は書き込みのたびに掃除する。

**表を足すだけ**で、既存の表には触れない。

Revision ID: login_attempts
Revises: silent_round_trip
Create Date: 2026-10-30

"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision = "login_attempts"
down_revision = "silent_round_trip"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "login_attempts",
        sa.Column("purpose", sa.String(length=32), nullable=False),
        sa.Column("identifier", sa.String(length=255), nullable=False),
        sa.Column("failures", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("window_started_at", sa.DateTime(), nullable=True),
        sa.Column("locked_until", sa.DateTime(), nullable=True),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.CheckConstraint("purpose IN ('login', 'password_reset')", name="ck_login_attempts_purpose"),
        sa.PrimaryKeyConstraint("purpose", "identifier"),
    )


def downgrade() -> None:
    op.drop_table("login_attempts")
