"""realign roles

ロールをアクターに揃える（ADR-0018）。

- ``member`` = 親（メンバー）: ``family:manage`` / ``point:manage`` を得る
- ``guest``  = 子（ゲスト）: ``family:view`` / ``point:view`` を得る
- ``manager`` = 運用者: family / point 系の scope を失う（家族機能とは無関係になる）
- ``admin``  = システム管理者: family / point 系の scope を失う（家族・ポイントは
  家庭の当事者の領分で、システム管理者は関与しない）

割り当ての引き直し:

- 子として家族に結び付いているアカウント（``family_memberships.role = 'child'``）は
  ``member`` から ``guest`` へ
- ``manager`` を持つアカウントは ``member`` へ。このリビジョンまで manager は
  「親」の役だった（運用者という位置付けはここから始まる）ので、保有者は
  家族への参加の有無に関わらず全員が親として扱われていたアカウントである

このリビジョン時点の姿を固定するため、付与の増減はこのファイルが持つ定数で
行う（0005 と同じ方針）。正本（master_data）は「今あるべき姿」を表すもので、
過去のリビジョンの姿ではない。

Revision ID: realign_roles
Revises: password_reset_cascade
Create Date: 2026-08-01

"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.engine import Connection

# revision identifiers, used by Alembic.
revision = "realign_roles"
down_revision = "password_reset_cascade"
branch_labels = None
depends_on = None

_FAMILY_SCOPES = ("family:view", "family:manage", "point:view", "point:manage")

# このリビジョンで増える付与 / 消える付与（ロール名 -> scope）
_ADDED_GRANTS: dict[str, tuple[str, ...]] = {
    "member": ("family:manage", "point:manage"),
    "guest": ("family:view", "point:view"),
}
_REMOVED_GRANTS: dict[str, tuple[str, ...]] = {
    "manager": _FAMILY_SCOPES,
    "admin": _FAMILY_SCOPES,
}

_roles = sa.table("roles", sa.column("id"), sa.column("name"))
_permissions = sa.table("permissions", sa.column("id"), sa.column("code"))
_role_permissions = sa.table("role_permissions", sa.column("role_id"), sa.column("permission_id"))
_user_roles = sa.table("user_roles", sa.column("user_id"), sa.column("role_id"))
_memberships = sa.table("family_memberships", sa.column("account_id"), sa.column("role"))


def _role_id(bind: Connection, name: str) -> int | None:
    found = bind.scalar(sa.select(_roles.c.id).where(_roles.c.name == name))
    return None if found is None else int(str(found))


def _permission_ids(bind: Connection, codes: tuple[str, ...]) -> dict[str, int]:
    rows = bind.execute(sa.select(_permissions.c.id, _permissions.c.code).where(_permissions.c.code.in_(codes))).all()
    return {str(code): int(str(row_id)) for row_id, code in rows}


def _apply_grants(bind: Connection, *, added: dict[str, tuple[str, ...]], removed: dict[str, tuple[str, ...]]) -> None:
    all_codes = tuple({code for codes in (*added.values(), *removed.values()) for code in codes})
    permission_ids = _permission_ids(bind, all_codes)
    for role_name, codes in removed.items():
        role_id = _role_id(bind, role_name)
        if role_id is None:
            continue
        ids = [permission_ids[code] for code in codes if code in permission_ids]
        if ids:
            bind.execute(
                _role_permissions.delete().where(
                    _role_permissions.c.role_id == role_id,
                    _role_permissions.c.permission_id.in_(ids),
                )
            )
    for role_name, codes in added.items():
        role_id = _role_id(bind, role_name)
        if role_id is None:
            continue
        for code in codes:
            _grant_once(bind, role_id=role_id, permission_id=permission_ids[code])


def _grant_once(bind: Connection, *, role_id: int, permission_id: int) -> None:
    exists = bind.scalar(
        sa.select(_role_permissions.c.role_id).where(
            _role_permissions.c.role_id == role_id,
            _role_permissions.c.permission_id == permission_id,
        )
    )
    if exists is None:
        bind.execute(_role_permissions.insert().values(role_id=role_id, permission_id=permission_id))


def _reassign(bind: Connection, *, user_ids: list[int], from_role: int, to_role: int) -> None:
    for user_id in user_ids:
        bind.execute(_user_roles.delete().where(_user_roles.c.user_id == user_id, _user_roles.c.role_id == from_role))
        held = bind.scalar(
            sa.select(_user_roles.c.user_id).where(_user_roles.c.user_id == user_id, _user_roles.c.role_id == to_role)
        )
        if held is None:
            bind.execute(_user_roles.insert().values(user_id=user_id, role_id=to_role))


def _holders_of(bind: Connection, role_id: int) -> list[int]:
    rows = bind.execute(sa.select(_user_roles.c.user_id).where(_user_roles.c.role_id == role_id)).all()
    return [int(str(user_id)) for (user_id,) in rows]


def _accounts_with_membership(bind: Connection, *, roles: tuple[str, ...]) -> set[int]:
    rows = bind.execute(
        sa.select(_memberships.c.account_id).where(
            _memberships.c.role.in_(roles), _memberships.c.account_id.is_not(None)
        )
    ).all()
    return {int(str(account_id)) for (account_id,) in rows}


def upgrade() -> None:
    bind = op.get_bind()
    _apply_grants(bind, added=_ADDED_GRANTS, removed=_REMOVED_GRANTS)

    manager = _role_id(bind, "manager")
    member = _role_id(bind, "member")
    guest = _role_id(bind, "guest")
    if manager is None or member is None or guest is None:
        return
    # 子として結び付いているアカウント: member -> guest
    children = _accounts_with_membership(bind, roles=("child",))
    _reassign(
        bind, user_ids=[uid for uid in _holders_of(bind, member) if uid in children], from_role=member, to_role=guest
    )
    # これまで親に使っていた manager: -> member
    _reassign(bind, user_ids=_holders_of(bind, manager), from_role=manager, to_role=member)


def downgrade() -> None:
    bind = op.get_bind()
    manager = _role_id(bind, "manager")
    member = _role_id(bind, "member")
    guest = _role_id(bind, "guest")
    if manager is not None and member is not None and guest is not None:
        # 親（owner / parent の参加を持つ member）: -> manager。
        # 参加を持たない member は旧姿でどちらだったか判別できないため member のまま残す
        guardians = _accounts_with_membership(bind, roles=("owner", "parent"))
        _reassign(
            bind,
            user_ids=[uid for uid in _holders_of(bind, member) if uid in guardians],
            from_role=member,
            to_role=manager,
        )
        # 子: guest -> member
        children = _accounts_with_membership(bind, roles=("child",))
        _reassign(
            bind,
            user_ids=[uid for uid in _holders_of(bind, guest) if uid in children],
            from_role=guest,
            to_role=member,
        )
    _apply_grants(
        bind,
        added={"manager": _FAMILY_SCOPES, "admin": _FAMILY_SCOPES},
        removed={"member": ("family:manage", "point:manage"), "guest": ("family:view", "point:view")},
    )
