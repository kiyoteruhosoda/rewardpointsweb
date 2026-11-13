"""family / append-only point ledger / username identifier

Schema replacement for ADR-0009, ADR-0010, and ADR-0011.

- Drop per-member sharing (``members`` / ``member_shares`` / ``point_entries``) and
  replace it with families (``families`` / ``family_memberships`` / ``point_ledgers`` /
  ``point_transactions`` / ``family_invitations``).
  This is before production use, so no data migration is written; the tables are swapped wholesale (ADR-0009).
- Separate the ``users`` identifier from the email address into ``username``. Existing accounts get
  the email address value in ``username``, and the display name that used to be ``username``
  moves to ``display_name`` (ADR-0011).

The definitions' source of truth is ``bounded_contexts/reward_points/infrastructure/reward_points_models.py``
and ``shared/infrastructure/models/user.py``.

Revision ID: family_point_ledger
Revises: default_admin_password
Create Date: 2026-08-01

"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.orm import Session

# revision identifiers, used by Alembic.
revision = "family_point_ledger"
down_revision = "default_admin_password"
branch_labels = None
depends_on = None

_BIGINT = sa.BigInteger().with_variant(sa.Integer(), "sqlite")
# Do not use DB-native ENUM (it becomes a VARCHAR with a CHECK constraint)
_FAMILY_ROLE = sa.Enum("owner", "parent", "child", name="family_role", native_enum=False)

_DROPPED_PERMISSION_CODES = ("member:view", "member:manage")
_ADDED_PERMISSION_CODES = ("family:view", "family:manage")


def _drop_legacy_member_tables() -> None:
    # Do not drop the indexes (they go away with the tables). Dropping an index on a foreign key column on its own
    # is rejected by MariaDB: ``Cannot drop index ...: needed in a foreign key
    # constraint`` (error 1553).
    op.drop_table("point_entries")
    op.drop_table("member_shares")
    op.drop_table("members")


def _create_family_tables() -> None:
    op.create_table(
        "families",
        sa.Column("id", _BIGINT, autoincrement=True, nullable=False),
        sa.Column("name", sa.String(length=100), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )

    op.create_table(
        "family_memberships",
        sa.Column("id", _BIGINT, autoincrement=True, nullable=False),
        sa.Column("family_id", _BIGINT, nullable=False),
        # A child just created by a parent has no account yet (ADR-0011)
        sa.Column("account_id", _BIGINT, nullable=True),
        sa.Column("role", _FAMILY_ROLE, nullable=False),
        sa.Column("display_name", sa.String(length=100), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["family_id"], ["families.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["account_id"], ["users.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("family_id", "account_id", name="uq_family_memberships_family_account"),
    )
    op.create_index(op.f("ix_family_memberships_family_id"), "family_memberships", ["family_id"])
    op.create_index(op.f("ix_family_memberships_account_id"), "family_memberships", ["account_id"])

    op.create_table(
        "point_ledgers",
        sa.Column("id", _BIGINT, autoincrement=True, nullable=False),
        sa.Column("family_id", _BIGINT, nullable=False),
        sa.Column("membership_id", _BIGINT, nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["family_id"], ["families.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["membership_id"], ["family_memberships.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        # One-to-one with the membership whose role = child (ADR-0009)
        sa.UniqueConstraint("membership_id"),
    )
    op.create_index(op.f("ix_point_ledgers_family_id"), "point_ledgers", ["family_id"])

    op.create_table(
        "point_transactions",
        sa.Column("id", _BIGINT, autoincrement=True, nullable=False),
        sa.Column("ledger_id", _BIGINT, nullable=False),
        sa.Column("amount", sa.Integer(), nullable=False),
        sa.Column("reason", sa.String(length=255), nullable=False),
        sa.Column("granted_by_membership_id", _BIGINT, nullable=True),
        sa.Column("occurred_at", sa.DateTime(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("reversal_of_id", _BIGINT, nullable=True),
        sa.Column("idempotency_key", sa.String(length=64), nullable=False),
        sa.ForeignKeyConstraint(["ledger_id"], ["point_ledgers.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["granted_by_membership_id"], ["family_memberships.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["reversal_of_id"], ["point_transactions.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("ledger_id", "idempotency_key", name="uq_point_transactions_idempotency"),
        sa.UniqueConstraint("reversal_of_id", name="uq_point_transactions_reversal_of"),
        sa.CheckConstraint("amount <> 0", name="ck_point_transactions_amount_nonzero"),
    )
    op.create_index(
        "ix_point_transactions_ledger_occurred",
        "point_transactions",
        ["ledger_id", "occurred_at", "id"],
    )

    op.create_table(
        "family_invitations",
        sa.Column("id", _BIGINT, autoincrement=True, nullable=False),
        sa.Column("family_id", _BIGINT, nullable=False),
        # Do not store the plaintext (it is returned only once, when issued)
        sa.Column("code_hash", sa.String(length=64), nullable=False),
        sa.Column("role", _FAMILY_ROLE, nullable=False),
        sa.Column("target_membership_id", _BIGINT, nullable=True),
        sa.Column("expires_at", sa.DateTime(), nullable=False),
        sa.Column("used_at", sa.DateTime(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["family_id"], ["families.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["target_membership_id"], ["family_memberships.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("code_hash"),
    )
    op.create_index(op.f("ix_family_invitations_family_id"), "family_invitations", ["family_id"])


def _split_username_from_email() -> None:
    """Make ``username`` the login identifier and move the display name to ``display_name``."""
    from shared.domain.auth import master_data

    # Do not put the rename and the addition of a column with the same name in one batch. SQLite batches
    # rebuild the table, so within one batch ``username`` would be both a "disappearing column" and
    # an "appearing column", and the column order could not be determined.
    with op.batch_alter_table("users") as batch:
        batch.alter_column("username", new_column_name="display_name", existing_type=sa.String(length=100))

    with op.batch_alter_table("users") as batch:
        batch.add_column(sa.Column("username", sa.String(length=255), nullable=True))
        batch.add_column(sa.Column("must_change_password", sa.Boolean(), nullable=False, server_default=sa.false()))
        batch.add_column(sa.Column("temporary_password_expires_at", sa.DateTime(), nullable=True))

    bind = op.get_bind()
    # Existing accounts' identifier is the email address value (ADR-0011)
    bind.execute(sa.text("UPDATE users SET username = LOWER(email)"))
    # Only the default administrator is aligned with the source-of-truth (master_data) value
    bind.execute(
        sa.text("UPDATE users SET username = :username WHERE id = :id"),
        {"username": master_data.DEFAULT_ADMIN_USERNAME, "id": master_data.DEFAULT_ADMIN_ID},
    )

    with op.batch_alter_table("users") as batch:
        batch.alter_column("username", existing_type=sa.String(length=255), nullable=False)
        batch.alter_column("email", existing_type=sa.String(length=255), nullable=True)
        batch.create_unique_constraint("uq_users_username", ["username"])


def upgrade() -> None:
    _drop_legacy_member_tables()
    _create_family_tables()
    _split_username_from_email()

    from shared.infrastructure.master_data_seeder import seed_master_data

    session = Session(bind=op.get_bind())
    _drop_permissions(session, _DROPPED_PERMISSION_CODES)
    seed_master_data(session)
    session.flush()


def downgrade() -> None:
    session = Session(bind=op.get_bind())
    _drop_permissions(session, _ADDED_PERMISSION_CODES)
    session.flush()

    with op.batch_alter_table("users") as batch:
        batch.drop_constraint("uq_users_username", type_="unique")
        batch.drop_column("username")
        batch.drop_column("temporary_password_expires_at")
        batch.drop_column("must_change_password")
        batch.alter_column("display_name", new_column_name="username", existing_type=sa.String(length=100))
        batch.alter_column("email", existing_type=sa.String(length=255), nullable=False)

    op.drop_table("family_invitations")
    op.drop_table("point_transactions")
    op.drop_table("point_ledgers")
    op.drop_table("family_memberships")
    op.drop_table("families")

    _recreate_legacy_member_tables()


def _drop_permissions(session: Session, codes: tuple[str, ...]) -> None:
    from shared.infrastructure.models import Permission, role_permissions

    permission_ids = [row_id for (row_id,) in session.query(Permission.id).filter(Permission.code.in_(codes)).all()]
    if permission_ids:
        session.execute(role_permissions.delete().where(role_permissions.c.permission_id.in_(permission_ids)))
    session.query(Permission).filter(Permission.code.in_(codes)).delete(synchronize_session=False)


def _recreate_legacy_member_tables() -> None:
    """Recreate the tables as of ADR-0007 (their contents are not restored)."""
    point_entry_type = sa.Enum("addition", "consumption", name="point_entry_type", native_enum=False)
    member_access_level = sa.Enum("view", "manage", name="member_access_level", native_enum=False)

    op.create_table(
        "members",
        sa.Column("id", _BIGINT, autoincrement=True, nullable=False),
        sa.Column("name", sa.String(length=100), nullable=False),
        sa.Column("owner_user_id", _BIGINT, nullable=False),
        sa.Column("linked_user_id", _BIGINT, nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["owner_user_id"], ["users.id"]),
        sa.ForeignKeyConstraint(["linked_user_id"], ["users.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("linked_user_id"),
    )
    op.create_index(op.f("ix_members_owner_user_id"), "members", ["owner_user_id"])

    op.create_table(
        "member_shares",
        sa.Column("member_id", _BIGINT, nullable=False),
        sa.Column("user_id", _BIGINT, nullable=False),
        sa.Column("access_level", member_access_level, nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["member_id"], ["members.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("member_id", "user_id"),
    )

    op.create_table(
        "point_entries",
        sa.Column("id", _BIGINT, autoincrement=True, nullable=False),
        sa.Column("member_id", _BIGINT, nullable=False),
        sa.Column("entry_type", point_entry_type, nullable=False),
        sa.Column("occurred_at", sa.DateTime(), nullable=False),
        sa.Column("points", sa.Integer(), nullable=False),
        sa.Column("reason", sa.String(length=255), nullable=True),
        sa.Column("application", sa.String(length=255), nullable=True),
        sa.Column("recorded_by_user_id", _BIGINT, nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["member_id"], ["members.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["recorded_by_user_id"], ["users.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_point_entries_member_id"), "point_entries", ["member_id"])
