"""password is optional (let the data represent users without local authentication)

Makes ``users.password_hash`` nullable and **sets the random values stored for users created
by SSO to NULL** (ADR-0034).

⚠ **Relaxing the column alone does not fix it.** If the random values stay, "has no password"
and "has a password nobody knows" remain indistinguishable, and a user who goes through a
password reset gains local authentication.

⚠ **Which rows hold a random value cannot be told from the value.** The only clue is
**whether the user row and the link to the IdP were created at the same time** - only when
created by SSO (``provision``) are the two born in the same transaction. For users later linked
to an existing account, the link is created days afterwards. Here the threshold is
**60 seconds**.

⚠ **A misclassification can only lock someone out, never add a way in.** If too many are cleared, those
users have an administrator set a password for them (a failure you notice). If too few are cleared,
an entrance silently stays open (a failure you do not notice). Since this is asymmetric, err on the side of clearing.

Revision ID: password_is_optional
Revises: backchannel_logout
Create Date: 2026-09-14

"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision = "password_is_optional"
down_revision = "backchannel_logout"
branch_labels = None
depends_on = None

#: Window (seconds) within which the user row and the link count as "created at the same time".
_PROVISIONED_WITHIN_SECONDS = 60

#: The expression for a difference in seconds differs by dialect (SQLite has no ``TIMESTAMPDIFF``).
_ELAPSED_SECONDS = {
    "sqlite": "(julianday(f.created_at) - julianday(u.created_at)) * 86400",
    "postgresql": "EXTRACT(EPOCH FROM (f.created_at - u.created_at))",
    "mysql": "TIMESTAMPDIFF(SECOND, u.created_at, f.created_at)",
    "mariadb": "TIMESTAMPDIFF(SECOND, u.created_at, f.created_at)",
}


def upgrade() -> None:
    # ⚠ **A bare ``alter_column`` produces SQL that SQLite cannot run** -
    #   it emits ``ALTER TABLE users ALTER COLUMN ... DROP NOT NULL`` (on MariaDB it turns into
    #   ``MODIFY``, so you cannot notice by looking only at production). Whether it works depends on
    #   the alembic version, so pin it down by rebuilding the table.
    with op.batch_alter_table("users") as batch:
        batch.alter_column("password_hash", existing_type=sa.String(length=255), nullable=True)
    elapsed = _ELAPSED_SECONDS.get(op.get_bind().dialect.name)
    if elapsed is None:
        # Do not touch unknown dialects. **Doing nothing is better than silently
        # clearing everyone's password** (remedy in docs/OPERATIONS.md).
        return
    op.execute(
        sa.text(
            "UPDATE users SET password_hash = NULL WHERE id IN ("
            " SELECT user_id FROM ("
            "  SELECT f.user_id AS user_id FROM federated_identities f"
            "  JOIN users u ON u.id = f.user_id"
            f"  WHERE {elapsed} BETWEEN 0 AND {_PROVISIONED_WITHIN_SECONDS}"
            " ) AS provisioned"
            ")"
        )
    )


def downgrade() -> None:
    # ⚠ **Cleared values do not come back.** Going back to NOT NULL with NULLs fails, so
    #   rows that cannot be refilled get **a value nobody knows** (matching the original shape).
    op.execute(sa.text("UPDATE users SET password_hash = 'pbkdf2:sha256:unusable' WHERE password_hash IS NULL"))
    with op.batch_alter_table("users") as batch:
        batch.alter_column("password_hash", existing_type=sa.String(length=255), nullable=False)
