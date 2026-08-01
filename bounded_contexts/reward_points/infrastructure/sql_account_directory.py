"""``IAccountDirectory`` / ``IAccountProvisioning`` の SQLAlchemy 実装。

アカウントはアプリ共通のユーザー（``shared/infrastructure/models/user.py``）。
このコンテキストが必要とするのは「ID から表示に必要な値を引く」「招待の受諾で
アカウントを作る」「一時パスワードを発行する」の 3 つだけで、一覧を配る口は
用意しない（``user:manage`` を持たない親に全アカウントを見せないため）。

家族の中での立場から、付与するアプリケーションロールを決める。親（メンバー）は
``member``、子（ゲスト）は ``guest``（ADR-0018。ADR-0009 の認可表と、ロールへの
権限付与が対応する）。
"""

from __future__ import annotations

import secrets
from collections.abc import Mapping, Sequence
from datetime import timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session
from werkzeug.security import generate_password_hash

from bounded_contexts.reward_points.domain.repositories.account_directory import (
    AccountRef,
    IAccountDirectory,
    IAccountProvisioning,
    TemporaryPassword,
)
from bounded_contexts.reward_points.domain.value_objects.family_role import FamilyRole
from shared.domain.auth.username import normalize_username
from shared.infrastructure.models import Role, User
from shared.kernel.settings.settings import settings
from shared.kernel.timestamps import utcnow

_ROLE_FOR_FAMILY_ROLE = {
    FamilyRole.OWNER: "member",
    FamilyRole.PARENT: "member",
    FamilyRole.CHILD: "guest",
}

# 保護者に必要な scope の全部。これらが全て揃っているアカウントに昇格は不要
_GUARDIAN_SCOPES = frozenset({"family:view", "family:manage", "point:view", "point:manage"})

# 一時パスワードは親が口頭で伝える前提。読み間違えにくい英数字だけを使う。
_TEMPORARY_ALPHABET = "abcdefghjkmnpqrstuvwxyz23456789"
_TEMPORARY_LENGTH = 10


class SqlAccountDirectory(IAccountDirectory):
    def __init__(self, session: Session) -> None:
        self._session = session

    def describe(self, account_ids: Sequence[int]) -> Mapping[int, AccountRef]:
        if not account_ids:
            return {}
        rows = self._session.scalars(select(User).where(User.id.in_(account_ids))).all()
        return {row.id: _to_ref(row) for row in rows}


class SqlAccountProvisioning(IAccountProvisioning):
    def __init__(self, session: Session) -> None:
        self._session = session

    def is_username_taken(self, username: str) -> bool:
        normalized = normalize_username(username)
        return self._session.scalar(select(User.id).where(User.username == normalized)) is not None

    def create_account(self, *, username: str, password: str, role: FamilyRole) -> AccountRef:
        normalized = normalize_username(username)
        user = User(
            username=normalized,
            # 子アカウントはメールアドレスを収集しない（ADR-0011）
            email=None,
            display_name=normalized,
            password_hash=generate_password_hash(password),
            is_active=True,
        )
        granted = self._session.scalar(select(Role).where(Role.name == _ROLE_FOR_FAMILY_ROLE[role]))
        if granted is not None:
            user.roles.append(granted)
        self._session.add(user)
        self._session.flush()
        return _to_ref(user)

    def grant_guardian_permissions(self, account_id: int) -> None:
        user = self._session.get(User, account_id)
        if user is None:  # 呼び出し側が membership から引いた ID なので通常は起きない
            raise ValueError(f"account not found: {account_id}")
        # admin のように保護者の scope を全て持つアカウントには何もしない。
        # ロールの構成へ触れる前に判定する — 判定より先に member を外すと、
        # 保護者側のロールが持たない scope（閲覧等）を黙って失い得る
        held = {permission.code for role in user.roles for permission in role.permissions}
        if held >= _GUARDIAN_SCOPES:
            return
        child_role = _ROLE_FOR_FAMILY_ROLE[FamilyRole.CHILD]
        guardian_role = _ROLE_FOR_FAMILY_ROLE[FamilyRole.PARENT]
        user.roles = [role for role in user.roles if role.name != child_role]
        if all(role.name != guardian_role for role in user.roles):
            granted = self._session.scalar(select(Role).where(Role.name == guardian_role))
            if granted is not None:
                user.roles.append(granted)
        self._session.flush()

    def delete_account(self, account_id: int) -> None:
        user = self._session.get(User, account_id)
        if user is None:  # 呼び出し側が membership から引いた ID なので通常は起きない
            raise ValueError(f"account not found: {account_id}")
        # 付随データ（パスキー・一時パスワード等）は外部キーの ON DELETE が追随する
        user.roles = []
        self._session.delete(user)
        self._session.flush()

    def issue_temporary_password(self, account_id: int) -> TemporaryPassword:
        user = self._session.get(User, account_id)
        if user is None:  # 呼び出し側が membership から引いた ID なので通常は起きない
            raise ValueError(f"account not found: {account_id}")
        password = "".join(secrets.choice(_TEMPORARY_ALPHABET) for _ in range(_TEMPORARY_LENGTH))
        expires_at = utcnow() + timedelta(seconds=settings.temporary_password_ttl_seconds)
        user.password_hash = generate_password_hash(password)
        user.must_change_password = True
        user.temporary_password_expires_at = expires_at
        self._session.flush()
        return TemporaryPassword(password=password, expires_at=expires_at)


def _to_ref(row: User) -> AccountRef:
    return AccountRef(
        account_id=row.id,
        username=row.username,
        display_name=row.display_name,
        email=row.email,
    )


__all__ = ["SqlAccountDirectory", "SqlAccountProvisioning"]
