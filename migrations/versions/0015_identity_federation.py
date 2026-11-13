"""identity federation

Adds the three tables needed for login through an external IdP (OpenID Connect) (ADR-0029).

- ``federated_identities`` - the link between an IdP account and a user. The key is
  ``(issuer, subject)``. There is no unique constraint on the user side (one person can have
  accounts at several IdPs).
- ``sso_login_sessions`` - a record of the authorization request. With several workers the process
  that sent the request and the one that receives the callback differ, so it lives in the DB.
- ``sso_login_tickets`` - one-time exchange tickets issued by the callback
  (only the hash is stored).

Once a user is deleted there is no point keeping the link or the tickets, so ``ON DELETE CASCADE``.
Existing users get no rows, so nothing looks different before and after this revision.

The definitions' source of truth is
``bounded_contexts/identity_federation/infrastructure/identity_federation_models.py``.

Revision ID: identity_federation
Revises: family_rules
Create Date: 2026-09-02

"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision = "identity_federation"
down_revision = "family_rules"
branch_labels = None
depends_on = None

_BIGINT = sa.BigInteger().with_variant(sa.Integer(), "sqlite")


def upgrade() -> None:
    op.create_table(
        "federated_identities",
        sa.Column("issuer", sa.String(255), primary_key=True),
        sa.Column("subject", sa.String(255), primary_key=True),
        sa.Column("user_id", _BIGINT, nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("last_login_at", sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
    )
    op.create_index("ix_federated_identities_user_id", "federated_identities", ["user_id"])

    op.create_table(
        "sso_login_sessions",
        sa.Column("state", sa.String(64), primary_key=True),
        sa.Column("nonce", sa.String(64), nullable=False),
        sa.Column("code_verifier", sa.String(128), nullable=False),
        sa.Column("binding_hash", sa.String(64), nullable=False),
        sa.Column("redirect_to", sa.String(255), nullable=False),
        sa.Column("expires_at", sa.DateTime(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
    )
    # Cleanup of expired rows runs on every issue. Add an index to look them up by expiry.
    op.create_index("ix_sso_login_sessions_expires_at", "sso_login_sessions", ["expires_at"])

    op.create_table(
        "sso_login_tickets",
        sa.Column("ticket_hash", sa.String(64), primary_key=True),
        sa.Column("user_id", _BIGINT, nullable=False),
        sa.Column("redirect_to", sa.String(255), nullable=False),
        sa.Column("expires_at", sa.DateTime(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
    )
    op.create_index("ix_sso_login_tickets_user_id", "sso_login_tickets", ["user_id"])
    op.create_index("ix_sso_login_tickets_expires_at", "sso_login_tickets", ["expires_at"])


def downgrade() -> None:
    # Indexes go away with the table. Dropping an index a foreign key uses first is rejected by MariaDB
    # (CLAUDE.md "DDL management")
    op.drop_table("sso_login_tickets")
    op.drop_table("sso_login_sessions")
    op.drop_table("federated_identities")
