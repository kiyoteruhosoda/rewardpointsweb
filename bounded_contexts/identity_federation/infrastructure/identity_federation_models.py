"""SQLAlchemy models of the identity federation context.

``migrations/env.py`` and ``tests/conftest.py`` import this module to register it
in the metadata (handling of context-specific models; CLAUDE.md "DDL management").
"""

from __future__ import annotations

import sqlalchemy as sa
from sqlalchemy.orm import Mapped, mapped_column

from shared.infrastructure.models.base import BigIntPk, utcnow
from shared.kernel.database.db import Base


class FederatedIdentityRecord(Base):
    """Link between an external IdP account and a user.

    The key is ``(issuer, subject)``. There is no unique constraint on the user side (one person can
    have multiple IdP accounts).
    """

    __tablename__ = "federated_identities"

    issuer: Mapped[str] = mapped_column(sa.String(255), primary_key=True)
    subject: Mapped[str] = mapped_column(sa.String(255), primary_key=True)
    user_id: Mapped[int] = mapped_column(
        BigIntPk,
        sa.ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    created_at = mapped_column(sa.DateTime(), nullable=False, default=utcnow)
    last_login_at = mapped_column(sa.DateTime(), nullable=True)


class SsoLoginSessionRecord(Base):
    """Record of an authorization request (from sending out until return).

    With multiple workers, the process that sent the browser out and the one it returns to differ, so
    this is kept in the DB rather than process memory.
    """

    __tablename__ = "sso_login_sessions"

    state: Mapped[str] = mapped_column(sa.String(64), primary_key=True)
    nonce: Mapped[str] = mapped_column(sa.String(64), nullable=False)
    code_verifier: Mapped[str] = mapped_column(sa.String(128), nullable=False)
    # Hash of the passphrase put into the sending browser's cookie (the raw value is not stored)
    binding_hash: Mapped[str] = mapped_column(sa.String(64), nullable=False)
    redirect_to: Mapped[str] = mapped_column(sa.String(255), nullable=False)
    expires_at = mapped_column(sa.DateTime(), nullable=False, index=True)
    created_at = mapped_column(sa.DateTime(), nullable=False, default=utcnow)
    # The user who started a linking round trip (ADR-0036). NULL for a login round trip.
    #
    # ⚠ **No foreign key.** This table holds short-lived records, not something to cascade
    #   when a user is deleted (records of deleted users disappear on expiry).
    link_user_id: Mapped[int | None] = mapped_column(BigIntPk, nullable=True)
    # A round trip tried without showing a screen (prompt=none; ADR-0052)
    silent: Mapped[bool] = mapped_column(sa.Boolean(), nullable=False, default=False, server_default=sa.false())
    # A round trip continuing an expired login (inside a hidden frame; ADR-0058). The return goes to the result page
    renewal: Mapped[bool] = mapped_column(sa.Boolean(), nullable=False, default=False, server_default=sa.false())


class SsoLoginTicketRecord(Base):
    """One-time exchange ticket issued by the callback (only the hash is stored).

    It also carries the IdP-side session (``issuer`` / ``subject`` / ``session_id``).
    Revocation propagation arrives addressed by this triple, so **unless it is recorded when the ticket
    is issued, it cannot be linked later** (ADR-0032).
    """

    __tablename__ = "sso_login_tickets"

    ticket_hash: Mapped[str] = mapped_column(sa.String(64), primary_key=True)
    user_id: Mapped[int] = mapped_column(
        BigIntPk,
        sa.ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    redirect_to: Mapped[str] = mapped_column(sa.String(255), nullable=False)
    issuer: Mapped[str] = mapped_column(sa.String(255), nullable=False, default="")
    subject: Mapped[str] = mapped_column(sa.String(255), nullable=False, default="")
    #: The ID token's ``sid``. Nullable, since some IdPs do not issue it.
    session_id: Mapped[str | None] = mapped_column(sa.String(255), nullable=True)
    #: The time the session started. Revocation records are matched against it (ADR-0032).
    session_started_at = mapped_column(sa.DateTime(), nullable=False, default=utcnow)
    expires_at = mapped_column(sa.DateTime(), nullable=False, index=True)
    created_at = mapped_column(sa.DateTime(), nullable=False, default=utcnow)


class FederatedSessionRevocationRecord(Base):
    """Record of a "stop this session" received from the IdP (ADR-0032).

    The primary key is ``jti`` so that resends are **rejected directly as duplicate rows**
    (the sender of idp ADR-0024 uses the same ``jti`` on resend).
    A row whose ``session_id`` is NULL applies to all sessions of that user.
    """

    __tablename__ = "federated_session_revocations"
    __table_args__ = (sa.Index("ix_federated_session_revocations_subject", "issuer", "subject"),)

    jti: Mapped[str] = mapped_column(sa.String(64), primary_key=True)
    issuer: Mapped[str] = mapped_column(sa.String(255), nullable=False)
    subject: Mapped[str] = mapped_column(sa.String(255), nullable=False)
    session_id: Mapped[str | None] = mapped_column(sa.String(255), nullable=True)
    revoked_at = mapped_column(sa.DateTime(), nullable=False)
    expires_at = mapped_column(sa.DateTime(), nullable=False, index=True)


__all__ = [
    "FederatedIdentityRecord",
    "FederatedSessionRevocationRecord",
    "SsoLoginSessionRecord",
    "SsoLoginTicketRecord",
]
