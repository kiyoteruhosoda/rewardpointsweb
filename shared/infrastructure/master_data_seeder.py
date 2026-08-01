"""マスタデータ投入（冪等）。

値の正本は ``shared/domain/auth/master_data.py``。ここには投入ロジックのみを
置き、``scripts/seed_master_data.py``・マイグレーション・テストから共用する。
"""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session
from werkzeug.security import generate_password_hash

from shared.domain.auth import master_data
from shared.infrastructure.models import Permission, Role, User


def seed_master_data(
    session: Session,
    *,
    admin_password: str | None = None,
    reset_admin_password: bool = False,
) -> None:
    """ロール・権限・初期管理者を投入する（冪等）。

    既存のロール・権限・管理者アカウントそのものは作り直さない。管理者の
    パスワードだけは :func:`reconcile_default_admin` の規則に従って追随する。
    """
    roles = _seed_roles(session)
    permissions = _seed_permissions(session)
    session.flush()

    _grant_role_permissions(roles, permissions)
    reconcile_default_admin(
        session,
        roles=roles,
        admin_password=admin_password,
        reset_password=reset_admin_password,
    )
    session.flush()


def reconcile_default_admin(
    session: Session,
    *,
    roles: dict[str, Role] | None = None,
    admin_password: str | None = None,
    reset_password: bool = False,
) -> bool:
    """既定の管理者アカウントを現在の既定値へ揃える。変更したら True を返す。

    パスワードを上書きするのは次の場合だけで、運用者が自分で決めたパスワードを
    黙って壊さない。

    - アカウントがまだ無い（新規作成）
    - 既定値のまま使われている（``SUPERSEDED_ADMIN_PASSWORD_HASHES`` に一致）。
      既定値を変更したときに、既存の環境も新しい既定値へ追随させるため。
    - *reset_password* が真（締め出されたときの復旧経路。呼び出し側が明示する）

    *admin_password* を渡すとその平文が、渡さなければ既定のハッシュが使われる。
    """
    admin = session.scalar(select(User).where(User.username == master_data.DEFAULT_ADMIN_USERNAME))
    password_hash = (
        generate_password_hash(admin_password) if admin_password else master_data.DEFAULT_ADMIN_PASSWORD_HASH
    )

    if admin is None:
        session.add(_build_default_admin(session, password_hash=password_hash, roles=roles))
        return True

    if reset_password or admin.password_hash in master_data.SUPERSEDED_ADMIN_PASSWORD_HASHES:
        admin.password_hash = password_hash
        return True
    return False


def _build_default_admin(session: Session, *, password_hash: str, roles: dict[str, Role] | None) -> User:
    admin = User(
        id=master_data.DEFAULT_ADMIN_ID,
        username=master_data.DEFAULT_ADMIN_USERNAME,
        email=master_data.DEFAULT_ADMIN_EMAIL,
        display_name=master_data.DEFAULT_ADMIN_DISPLAY_NAME,
        password_hash=password_hash,
        is_active=True,
    )
    role = (roles or {}).get(master_data.DEFAULT_ADMIN_ROLE) or session.scalar(
        select(Role).where(Role.name == master_data.DEFAULT_ADMIN_ROLE)
    )
    if role is not None:
        admin.roles.append(role)
    return admin


def _seed_roles(session: Session) -> dict[str, Role]:
    roles: dict[str, Role] = {}
    for role_id, name in master_data.ROLES:
        role = session.scalar(select(Role).where(Role.name == name))
        if role is None:
            role = Role(id=role_id, name=name)
            session.add(role)
        roles[name] = role
    return roles


def _seed_permissions(session: Session) -> dict[str, Permission]:
    permissions: dict[str, Permission] = {}
    for code in master_data.PERMISSION_CODES:
        permission = session.scalar(select(Permission).where(Permission.code == code))
        if permission is None:
            permission = Permission(code=code)
            session.add(permission)
        permissions[code] = permission
    return permissions


def _grant_role_permissions(roles: dict[str, Role], permissions: dict[str, Permission]) -> None:
    for role_name, codes in master_data.ROLE_PERMISSIONS.items():
        role = roles[role_name]
        existing = {p.code for p in role.permissions}
        for code in codes:
            if code not in existing:
                role.permissions.append(permissions[code])


__all__ = ["reconcile_default_admin", "seed_master_data"]
