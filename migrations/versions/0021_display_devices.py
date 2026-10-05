"""display devices (表示端末のペアリング)

表示端末（サイネージ）をペアリングで入れる（ADR-0047）。

- 家族の中の立場に ``display`` を足す。``family_memberships.role`` と
  ``family_invitations.role`` は ``native_enum=False`` の VARCHAR で、長さが
  いちばん長い値（``parent`` の 6 字）で決まっている。``display`` は 7 字なので広げる
- ペアリング（``display_pairings``）と端末の資格情報（``display_credentials``）の表を足す
- scope ``display:approve`` と、ロール ``operator``（運用管理者）・``display``（表示端末）を足す。
  ⚠ **admin には ``display:approve`` を付けない**（admin は家庭の台帳を見ない。ADR-0018）

付与はこのファイルが持つ定数で行う（0005・0010 と同じ方針。正本の master_data は
「今あるべき姿」で、このリビジョンの姿ではない）。ロールは id を決め打たずに名前で足す
——管理画面でロールを作った環境では、5・6 番がもう使われていることがある。

定義の正本は ``bounded_contexts/display_devices/infrastructure/display_devices_models.py``。

Revision ID: display_devices
Revises: reward_event_deadline
Create Date: 2026-10-05

"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.engine import Connection

# revision identifiers, used by Alembic.
revision = "display_devices"
down_revision = "reward_event_deadline"
branch_labels = None
depends_on = None

_BIGINT = sa.BigInteger().with_variant(sa.Integer(), "sqlite")
_ROLE_BEFORE = sa.Enum("owner", "parent", "child", name="family_role", native_enum=False)
_ROLE_AFTER = sa.Enum("owner", "parent", "child", "display", name="family_role", native_enum=False)
_ROLE_TABLES = ("family_memberships", "family_invitations")

_APPROVE = "display:approve"
# このリビジョンで足すロールと、その scope
_ADDED_ROLES: dict[str, tuple[str, ...]] = {
    "operator": ("dashboard:view", "gui:view", _APPROVE),
    "display": ("dashboard:view", "gui:view", "family:view", "point:view"),
}

_roles = sa.table("roles", sa.column("id"), sa.column("name"))
_permissions = sa.table("permissions", sa.column("id"), sa.column("code"))
_role_permissions = sa.table("role_permissions", sa.column("role_id"), sa.column("permission_id"))
_user_roles = sa.table("user_roles", sa.column("user_id"), sa.column("role_id"))
_memberships = sa.table("family_memberships", sa.column("role"))


def upgrade() -> None:
    for table in _ROLE_TABLES:
        with op.batch_alter_table(table) as batch:
            batch.alter_column("role", existing_type=_ROLE_BEFORE, type_=_ROLE_AFTER, existing_nullable=False)
    _create_tables()
    _seed_roles(op.get_bind())


def _create_tables() -> None:
    op.create_table(
        "display_pairings",
        sa.Column("id", _BIGINT, primary_key=True, autoincrement=True),
        sa.Column("user_code_hash", sa.String(64), nullable=False),
        sa.Column("device_code_hash", sa.String(64), nullable=False),
        sa.Column("expires_at", sa.DateTime(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("approved_account_id", _BIGINT, nullable=True),
        sa.Column("approved_at", sa.DateTime(), nullable=True),
        sa.Column("claimed_at", sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(["approved_account_id"], ["users.id"], ondelete="CASCADE"),
        sa.UniqueConstraint("user_code_hash"),
        sa.UniqueConstraint("device_code_hash"),
    )
    # 期限切れの掃除がペアリングを始めるたびに走る。期限で引ける索引を置く
    op.create_index("ix_display_pairings_expires_at", "display_pairings", ["expires_at"])
    op.create_index("ix_display_pairings_approved_account_id", "display_pairings", ["approved_account_id"])
    op.create_table(
        "display_credentials",
        sa.Column("account_id", _BIGINT, primary_key=True),
        sa.Column("credential_hash", sa.String(64), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("last_used_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["account_id"], ["users.id"], ondelete="CASCADE"),
        sa.UniqueConstraint("credential_hash"),
    )


def _role_id(bind: Connection, name: str) -> int | None:
    found = bind.scalar(sa.select(_roles.c.id).where(_roles.c.name == name))
    return None if found is None else int(str(found))


def _permission_id(bind: Connection, code: str) -> int | None:
    found = bind.scalar(sa.select(_permissions.c.id).where(_permissions.c.code == code))
    return None if found is None else int(str(found))


def _seed_roles(bind: Connection) -> None:
    if _permission_id(bind, _APPROVE) is None:
        bind.execute(_permissions.insert().values(code=_APPROVE))
    for role_name, codes in _ADDED_ROLES.items():
        role_id = _role_id(bind, role_name)
        if role_id is None:
            bind.execute(_roles.insert().values(name=role_name))
            role_id = _role_id(bind, role_name)
        for code in codes:
            permission_id = _permission_id(bind, code)
            if role_id is None or permission_id is None:
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
    # 戻した後の列には ``display`` が入らない。表示端末の参加を先に外す
    # （アカウントはロールを失って残る。管理画面から消せる）
    bind.execute(_memberships.delete().where(_memberships.c.role == "display"))
    _drop_roles(bind)
    op.drop_table("display_credentials")
    op.drop_table("display_pairings")
    for table in _ROLE_TABLES:
        with op.batch_alter_table(table) as batch:
            batch.alter_column("role", existing_type=_ROLE_AFTER, type_=_ROLE_BEFORE, existing_nullable=False)


def _drop_roles(bind: Connection) -> None:
    for role_name in _ADDED_ROLES:
        role_id = _role_id(bind, role_name)
        if role_id is None:
            continue
        bind.execute(_user_roles.delete().where(_user_roles.c.role_id == role_id))
        bind.execute(_role_permissions.delete().where(_role_permissions.c.role_id == role_id))
        bind.execute(_roles.delete().where(_roles.c.id == role_id))
    permission_id = _permission_id(bind, _APPROVE)
    if permission_id is not None:
        bind.execute(_role_permissions.delete().where(_role_permissions.c.permission_id == permission_id))
        bind.execute(_permissions.delete().where(_permissions.c.id == permission_id))
