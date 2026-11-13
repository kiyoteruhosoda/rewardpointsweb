"""SQLAlchemy implementations of ``IAccountDirectory`` / ``IAccountProvisioning``.

Accounts are the app-wide users (``shared/infrastructure/models/user.py``).
This context needs only three things: "look up display values by ID", "create
an account when an invitation is accepted" and "issue a temporary password".
There is no entry point that hands out a list (so parents without
``user:manage`` cannot see every account).

The application role to grant is decided from the role in the family: parents
(members) get ``member``, children (guests) get ``guest`` (ADR-0018; the
permissions granted to the roles correspond to the authorization table of
ADR-0009).
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
    FamilyRole.DISPLAY: "display",
}

# Prefix of display devices' login identifiers. Nobody types it, so it only needs to be recognizable as a device
_DISPLAY_USERNAME_PREFIX = "display-"

# All scopes a guardian needs. An account that has all of them needs no promotion
_GUARDIAN_SCOPES = frozenset({"family:view", "family:manage", "point:view", "point:manage"})

# Temporary passwords are meant to be read out by a parent, so use only hard-to-misread alphanumerics.
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

    def create_account(
        self, *, username: str, password: str, role: FamilyRole, display_name: str | None = None
    ) -> AccountRef:
        normalized = normalize_username(username)
        chosen_name = display_name.strip() if display_name else ""
        user = User(
            username=normalized,
            # Child accounts do not collect an email address (ADR-0011)
            email=None,
            # Without a preferred name, show the login identifier as is
            display_name=chosen_name or normalized,
            password_hash=generate_password_hash(password),
            is_active=True,
        )
        granted = self._session.scalar(select(Role).where(Role.name == _ROLE_FOR_FAMILY_ROLE[role]))
        if granted is not None:
            user.roles.append(granted)
        self._session.add(user)
        self._session.flush()
        return _to_ref(user)

    def create_display_account(self, *, display_name: str) -> AccountRef:
        user = User(
            username=f"{_DISPLAY_USERNAME_PREFIX}{secrets.token_hex(8)}",
            email=None,
            display_name=display_name,
            # ⚠ Has no password entry point (ADR-0034, ADR-0047)
            password_hash=None,
            is_active=True,
        )
        granted = self._session.scalar(select(Role).where(Role.name == _ROLE_FOR_FAMILY_ROLE[FamilyRole.DISPLAY]))
        if granted is not None:
            user.roles.append(granted)
        self._session.add(user)
        self._session.flush()
        return _to_ref(user)

    def grant_guardian_permissions(self, account_id: int) -> None:
        user = self._session.get(User, account_id)
        if user is None:  # Normally cannot happen: the caller got the ID from a membership
            raise ValueError(f"account not found: {account_id}")
        # Do nothing for an account that already has every guardian scope, such as admin.
        # Check before touching the roles: removing member before the check could
        # silently drop scopes (viewing etc.) that the guardian role does not have
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
        if user is None:  # Normally cannot happen: the caller got the ID from a membership
            raise ValueError(f"account not found: {account_id}")
        # Dependent data (passkeys, temporary passwords etc.) follows via the foreign keys' ON DELETE
        user.roles = []
        self._session.delete(user)
        self._session.flush()

    def issue_temporary_password(self, account_id: int) -> TemporaryPassword:
        user = self._session.get(User, account_id)
        if user is None:  # Normally cannot happen: the caller got the ID from a membership
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
