"""gachas (machines, prizes, draws) and the gacha:draw scope

Gacha machines per child ledger (ADR-0060). A machine (``gachas``) holds its prizes
(``gacha_prizes``); each draw is one row in ``gacha_draws`` with a snapshot of what it won.
Deleting a ledger deletes all three; deleting a machine keeps its draws (``SET NULL``).

Also adds the ``gacha:draw`` permission and grants it to ``member`` (parents) and ``guest``
(children). The seeder only runs on fresh databases, so existing environments get the grant
here. The codes are this file's own constants, not the source of truth in
``shared/domain/auth/master_data.py`` (that file describes "now", not this revision).

The definitions' source of truth is ``bounded_contexts/reward_points/infrastructure/reward_points_models.py``.

Revision ID: gachas
Revises: renewal_round_trip
Create Date: 2026-11-15

"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.engine import Connection

# revision identifiers, used by Alembic.
revision = "gachas"
down_revision = "renewal_round_trip"
branch_labels = None
depends_on = None

_BIGINT = sa.BigInteger().with_variant(sa.Integer(), "sqlite")

_PERMISSION = "gacha:draw"
_GRANTED_ROLES = ("member", "guest")

_roles = sa.table("roles", sa.column("id"), sa.column("name"))
_permissions = sa.table("permissions", sa.column("id"), sa.column("code"))
_role_permissions = sa.table("role_permissions", sa.column("role_id"), sa.column("permission_id"))


def upgrade() -> None:
    op.create_table(
        "gachas",
        sa.Column("id", _BIGINT, primary_key=True, autoincrement=True),
        sa.Column("ledger_id", _BIGINT, nullable=False),
        sa.Column("name", sa.String(50), nullable=False),
        sa.Column("price", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["ledger_id"], ["point_ledgers.id"], ondelete="CASCADE"),
        sa.CheckConstraint("price > 0", name="ck_gachas_price_positive"),
    )
    op.create_index("ix_gachas_ledger_id", "gachas", ["ledger_id"])
    op.create_table(
        "gacha_prizes",
        sa.Column("id", _BIGINT, primary_key=True, autoincrement=True),
        sa.Column("gacha_id", _BIGINT, nullable=False),
        sa.Column("position", sa.Integer(), nullable=False),
        sa.Column("name", sa.String(50), nullable=False),
        sa.Column("weight", sa.Integer(), nullable=False),
        sa.Column("is_miss", sa.Boolean(), nullable=False),
        sa.ForeignKeyConstraint(["gacha_id"], ["gachas.id"], ondelete="CASCADE"),
        sa.UniqueConstraint("gacha_id", "position", name="uq_gacha_prizes_position"),
        sa.CheckConstraint("weight >= 1", name="ck_gacha_prizes_weight_positive"),
    )
    op.create_table(
        "gacha_draws",
        sa.Column("id", _BIGINT, primary_key=True, autoincrement=True),
        sa.Column("ledger_id", _BIGINT, nullable=False),
        sa.Column("gacha_id", _BIGINT, nullable=True),
        sa.Column("gacha_name", sa.String(50), nullable=False),
        sa.Column("prize_name", sa.String(50), nullable=False),
        sa.Column("is_miss", sa.Boolean(), nullable=False),
        sa.Column("price", sa.Integer(), nullable=False),
        sa.Column("idempotency_key", sa.String(64), nullable=False),
        sa.Column("transaction_id", _BIGINT, nullable=True),
        sa.Column("drawn_by_membership_id", _BIGINT, nullable=True),
        sa.Column("drawn_at", sa.DateTime(), nullable=False),
        sa.Column("handed_over_at", sa.DateTime(), nullable=True),
        sa.Column("handed_over_by_membership_id", _BIGINT, nullable=True),
        sa.ForeignKeyConstraint(["ledger_id"], ["point_ledgers.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["gacha_id"], ["gachas.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["transaction_id"], ["point_transactions.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["drawn_by_membership_id"], ["family_memberships.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["handed_over_by_membership_id"], ["family_memberships.id"], ondelete="SET NULL"),
        sa.UniqueConstraint("ledger_id", "idempotency_key", name="uq_gacha_draws_idempotency"),
        sa.UniqueConstraint("transaction_id", name="uq_gacha_draws_transaction"),
        sa.CheckConstraint("price > 0", name="ck_gacha_draws_price_positive"),
    )
    op.create_index("ix_gacha_draws_ledger_drawn", "gacha_draws", ["ledger_id", "drawn_at", "id"])
    _grant_draw_permission(op.get_bind())


def _grant_draw_permission(bind: Connection) -> None:
    permission_id = bind.scalar(sa.select(_permissions.c.id).where(_permissions.c.code == _PERMISSION))
    if permission_id is None:
        bind.execute(_permissions.insert().values(code=_PERMISSION))
        permission_id = bind.scalar(sa.select(_permissions.c.id).where(_permissions.c.code == _PERMISSION))
    for role_name in _GRANTED_ROLES:
        role_id = bind.scalar(sa.select(_roles.c.id).where(_roles.c.name == role_name))
        if role_id is None:
            continue
        granted = bind.scalar(
            sa.select(_role_permissions.c.role_id).where(
                _role_permissions.c.role_id == role_id, _role_permissions.c.permission_id == permission_id
            )
        )
        if granted is None:
            bind.execute(_role_permissions.insert().values(role_id=role_id, permission_id=permission_id))


def downgrade() -> None:
    bind = op.get_bind()
    permission_id = bind.scalar(sa.select(_permissions.c.id).where(_permissions.c.code == _PERMISSION))
    if permission_id is not None:
        bind.execute(_role_permissions.delete().where(_role_permissions.c.permission_id == permission_id))
        bind.execute(_permissions.delete().where(_permissions.c.id == permission_id))
    # Indexes go away with the table. Dropping an index a foreign key uses first is rejected by MariaDB
    # (CLAUDE.md "DDL management")
    op.drop_table("gacha_draws")
    op.drop_table("gacha_prizes")
    op.drop_table("gachas")
