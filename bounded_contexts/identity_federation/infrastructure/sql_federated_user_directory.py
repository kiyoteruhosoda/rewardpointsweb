"""SQLAlchemy implementation of the gateway to users (``users``).

Only this touches the ``shared`` ``User`` model; the identity federation Domain / Application
layers do not know this implementation.

**The only thing it creates is an account for a first-time user** (ADR-0041). Its shape matches the admin
screen defaults.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from bounded_contexts.identity_federation.domain.entities.federated_account import (
    FederatedAccount,
)
from shared.infrastructure.models import Role, User

logger = logging.getLogger(__name__)

#: Column width of ``users.display_name``. ⚠ **Long names are truncated.** MySQL in strict mode
#: does not accept overflowing values, so without truncation **updating the copy breaks login**.
_DISPLAY_NAME_LIMIT = 100

#: Role of created accounts. ⚠ **Parent (``member``), the same default as the admin screen** (ADR-0018).
#: Not in a family yet; they create a family or join one by invitation.
_ROLE_FOR_NEW_ACCOUNT = "member"


@dataclass(frozen=True)
class SqlFederatedUserDirectory:
    session: Session

    def find_by_id(self, user_id: int) -> FederatedAccount | None:
        return _as_account(self.session.get(User, user_id))

    def find_by_email(self, email: str) -> FederatedAccount | None:
        """Look up by email address.

        ``users.email`` is optional and may be NULL (ADR-0011). In SQL comparison,
        NULL never equals any value, so users without an email address
        (children) never match here. An empty string skips matching altogether
        -- so it does not pair up with users whose ``email`` column is empty.
        """
        if not email:
            return None
        return _as_account(self.session.scalar(select(User).where(User.email == email)))

    def find_by_username(self, username: str) -> FederatedAccount | None:
        return _as_account(self.session.scalar(select(User).where(User.username == username)))

    def provision(self, *, username: str, email: str | None, display_name: str) -> FederatedAccount | None:
        """Create an account for a first-time user (ADR-0041).

        ⚠ **If a unique column collides, ``None``.** Between checking and creating, another round trip
        of the same person may come back. Only the half-created row should be rolled back, so
        it is written inside a savepoint (the outer round trip's record stays consumed).
        """
        roles = list(self.session.scalars(select(Role).where(Role.name == _ROLE_FOR_NEW_ACCOUNT)))
        user = User(
            username=username,
            email=email,
            display_name=display_name[:_DISPLAY_NAME_LIMIT],
            # ⚠ **NULL means "no local password"** (ADR-0034). The only way in is the IdP.
            password_hash=None,
            is_active=True,
        )
        try:
            with self.session.begin_nested():
                user.roles = roles
                self.session.add(user)
                self.session.flush()
        except IntegrityError:
            return None
        return _as_account(user)

    def refresh_profile(self, user_id: int, *, email: str | None, display_name: str) -> None:
        """Overwrite the copy with the name and email address (ADR-0038).

        ⚠ **Do not write colliding values.** ``users.email`` is unique, so writing a value
        another user already has would **make login fail with 500**. Breaking login by
        updating the copy would defeat the purpose, so just that field is skipped and recorded.

        ⚠ **Do not touch ``username``.** It is this app's login identifier, not the IdP's
        asserted name (ADR-0011). Rewriting it would remove the way in for people who used a password.
        """
        user = self.session.get(User, user_id)
        if user is None:  # pragma: no cover - only if the user just looked up has disappeared
            return
        if email is not None and email != user.email and self._email_is_free(email, user_id):
            user.email = email
        name = display_name[:_DISPLAY_NAME_LIMIT]
        if name and name != user.display_name:
            user.display_name = name
        self.session.flush()

    def _email_is_free(self, email: str, user_id: int) -> bool:
        taken = self.session.scalar(select(User.id).where(User.email == email).where(User.id != user_id))
        if taken is not None:
            # ⚠ Do not keep the value itself (PII). Knowing which field was skipped is enough.
            logger.warning("federated_profile_conflict", extra={"field": "email"})
            return False
        return True


def _as_account(user: User | None) -> FederatedAccount | None:
    return None if user is None else FederatedAccount(user_id=user.id, is_active=user.is_active)


__all__ = ["SqlFederatedUserDirectory"]
