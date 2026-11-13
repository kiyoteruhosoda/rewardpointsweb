"""login attempts

Per-name records of failures (ADR-0055). They live in the DB rather than in process memory because
Gunicorn runs several workers (otherwise each worker would allow its own set of attempts).

The primary key is (purpose, name). The name is **the username that was sent**, and it is not
tied to an existing account (counting only existing ones would reveal whether an account exists
by whether the attempt is refused). Expired rows are cleaned up on every write.

**It only adds a table** and does not touch existing tables.

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
