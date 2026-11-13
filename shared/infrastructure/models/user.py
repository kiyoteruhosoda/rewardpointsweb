"""Models for users and password reset tokens.

The login identifier is ``username`` (UNIQUE) and ``email`` is optional (ADR-0011).
They are separated so accounts without an email address (children) can be created;
when set, the email is used for notifications and password resets as before.

``display_name`` is the name shown on screen. It is kept apart from the identifier, so changing
the name does not change how one logs in.
"""

from __future__ import annotations

import sqlalchemy as sa
from sqlalchemy.orm import Mapped, mapped_column, relationship

from shared.infrastructure.models.base import BigIntPk, utcnow
from shared.kernel.database.db import Base

user_roles = sa.Table(
    "user_roles",
    Base.metadata,
    sa.Column("user_id", BigIntPk, sa.ForeignKey("users.id"), primary_key=True),
    sa.Column("role_id", BigIntPk, sa.ForeignKey("roles.id"), primary_key=True),
)


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(BigIntPk, primary_key=True, autoincrement=True)
    # Login identifier. Stored normalized to lowercase (shared/domain/auth/username.py)
    username: Mapped[str] = mapped_column(sa.String(255), unique=True, nullable=False)
    # Optional. When set, used for notifications and password resets
    email: Mapped[str | None] = mapped_column(sa.String(255), unique=True, nullable=True)
    display_name: Mapped[str] = mapped_column(sa.String(100), nullable=False)
    #: ⚠ **NULL means "no local password"** (ADR-0034). It is neither "an empty password"
    #: nor "a value nobody knows". Check it through :attr:`has_local_password`.
    password_hash: Mapped[str | None] = mapped_column(sa.String(255), nullable=True)
    is_active: Mapped[bool] = mapped_column(sa.Boolean(), nullable=False, default=True, server_default=sa.true())
    # Logged in with a temporary password. No other action is allowed until it is changed
    must_change_password: Mapped[bool] = mapped_column(
        sa.Boolean(), nullable=False, default=False, server_default=sa.false()
    )
    # Expiry of the temporary password (NULL for a normal password)
    temporary_password_expires_at = mapped_column(sa.DateTime(), nullable=True)
    created_at = mapped_column(sa.DateTime(), nullable=False, default=utcnow)
    updated_at = mapped_column(sa.DateTime(), nullable=False, default=utcnow, onupdate=utcnow)

    roles = relationship("Role", secondary=user_roles, lazy="selectin")

    @property
    def has_local_password(self) -> bool:
        """Whether this user can sign in to this app with a password (ADR-0034).

        ⚠ **Do not read false as "not decided yet".** False means "this user has
        no password entry point", and a reset does not create one either. A password is
        given only when an admin sets one explicitly.
        """
        return self.password_hash is not None

    @property
    def permission_codes(self) -> frozenset[str]:
        """Effective scope = union of the permissions of all roles."""
        return frozenset(p.code for r in self.roles for p in r.permissions)


class PasswordResetToken(Base):
    __tablename__ = "password_reset_tokens"

    id: Mapped[int] = mapped_column(BigIntPk, primary_key=True, autoincrement=True)
    # Deleted along with the account (CASCADE rather than reject; a token
    # means nothing without its owner)
    user_id: Mapped[int] = mapped_column(
        BigIntPk, sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    token_hash: Mapped[str] = mapped_column(sa.String(64), unique=True, nullable=False)
    expires_at = mapped_column(sa.DateTime(), nullable=False)
    used_at = mapped_column(sa.DateTime(), nullable=True)
    created_at = mapped_column(sa.DateTime(), nullable=False, default=utcnow)


__all__ = ["PasswordResetToken", "User", "user_roles"]
