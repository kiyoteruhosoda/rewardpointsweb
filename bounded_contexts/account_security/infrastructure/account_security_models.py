"""SQLAlchemy models of the account security context.

``migrations/env.py`` and ``tests/conftest.py`` import this module to register it in the
metadata (handling of context-specific models; CLAUDE.md "DDL management").
"""

from __future__ import annotations

import sqlalchemy as sa
from sqlalchemy.orm import Mapped, mapped_column

from bounded_contexts.account_security.domain.entities.login_attempts import ATTEMPT_PURPOSES
from bounded_contexts.account_security.domain.entities.webauthn_challenge import (
    CHALLENGE_PURPOSES,
)
from shared.infrastructure.models.base import BigIntPk, utcnow
from shared.kernel.database.db import Base


class TotpSecretRecord(Base):
    """TOTP shared key (one row per user)."""

    __tablename__ = "totp_secrets"

    user_id: Mapped[int] = mapped_column(BigIntPk, sa.ForeignKey("users.id", ondelete="CASCADE"), primary_key=True)
    secret: Mapped[str] = mapped_column(sa.String(64), nullable=False)
    # While NULL, "enrollment in progress". Two-factor authentication is not enabled yet.
    confirmed_at = mapped_column(sa.DateTime(), nullable=True)
    created_at = mapped_column(sa.DateTime(), nullable=False, default=utcnow)
    updated_at = mapped_column(sa.DateTime(), nullable=False, default=utcnow, onupdate=utcnow)


class PasskeyCredentialRecord(Base):
    """WebAuthn credential (passkey)."""

    __tablename__ = "passkey_credentials"

    id: Mapped[int] = mapped_column(BigIntPk, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(
        BigIntPk,
        sa.ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    # base64url string. At authentication the owner is looked up by this value.
    credential_id: Mapped[str] = mapped_column(sa.String(255), unique=True, nullable=False)
    public_key: Mapped[str] = mapped_column(sa.Text(), nullable=False)
    sign_count: Mapped[int] = mapped_column(
        sa.BigInteger().with_variant(sa.Integer(), "sqlite"),
        nullable=False,
        default=0,
    )
    transports = mapped_column(sa.JSON(), nullable=True)
    name: Mapped[str | None] = mapped_column(sa.String(100), nullable=True)
    attestation_format: Mapped[str | None] = mapped_column(sa.String(64), nullable=True)
    aaguid: Mapped[str | None] = mapped_column(sa.String(64), nullable=True)
    backup_eligible: Mapped[bool] = mapped_column(
        sa.Boolean(), nullable=False, default=False, server_default=sa.false()
    )
    backup_state: Mapped[bool] = mapped_column(sa.Boolean(), nullable=False, default=False, server_default=sa.false())
    last_used_at = mapped_column(sa.DateTime(), nullable=True)
    created_at = mapped_column(sa.DateTime(), nullable=False, default=utcnow)
    updated_at = mapped_column(sa.DateTime(), nullable=False, default=utcnow, onupdate=utcnow)


class WebAuthnChallengeRecord(Base):
    """Issued challenges.

    Gunicorn runs with multiple workers, so the issuing process and the verifying process
    may differ. They live in the DB rather than in process memory.
    """

    __tablename__ = "webauthn_challenges"

    challenge_id: Mapped[str] = mapped_column(sa.String(32), primary_key=True)
    challenge: Mapped[str] = mapped_column(sa.String(255), nullable=False)
    # Use VARCHAR with CHECK instead of a DB-native ENUM (CLAUDE.md)
    purpose: Mapped[str] = mapped_column(
        sa.Enum(*CHALLENGE_PURPOSES, name="webauthn_challenge_purpose", native_enum=False),
        nullable=False,
    )
    # Nullable, because for login challenges the user is unknown at issue time
    user_id: Mapped[int | None] = mapped_column(BigIntPk, sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=True)
    expires_at = mapped_column(sa.DateTime(), nullable=False, index=True)
    created_at = mapped_column(sa.DateTime(), nullable=False, default=utcnow)


class LoginAttemptRecord(Base):
    """Failure record per identifier (ADR-0055).

    The identifier is **the username that was sent** and is not tied to ``users``. Counting only
    existing accounts would reveal existence by whether the request is refused.
    Expired rows are cleaned up on every write.
    """

    __tablename__ = "login_attempts"
    __table_args__ = (sa.CheckConstraint(f"purpose IN {ATTEMPT_PURPOSES}", name="ck_login_attempts_purpose"),)

    purpose: Mapped[str] = mapped_column(sa.String(32), primary_key=True)
    identifier: Mapped[str] = mapped_column(sa.String(255), primary_key=True)
    failures: Mapped[int] = mapped_column(sa.Integer(), nullable=False, default=0, server_default="0")
    window_started_at = mapped_column(sa.DateTime(), nullable=True)
    locked_until = mapped_column(sa.DateTime(), nullable=True)
    updated_at = mapped_column(sa.DateTime(), nullable=False, default=utcnow, onupdate=utcnow)


__all__ = [
    "LoginAttemptRecord",
    "PasskeyCredentialRecord",
    "TotpSecretRecord",
    "WebAuthnChallengeRecord",
]
