"""SQLAlchemy models for the display devices context (ADR-0047).

``migrations/env.py`` and ``tests/conftest.py`` import this module to register it in
the metadata (how context-specific models are handled; CLAUDE.md "DDL management").

Confirmation codes, device secrets and device credentials are all stored only as SHA-256 hashes.
"""

from __future__ import annotations

import sqlalchemy as sa
from sqlalchemy.orm import Mapped, mapped_column

from shared.infrastructure.models.base import BigIntPk, utcnow
from shared.kernel.database.db import Base


class DisplayPairingRecord(Base):
    """One pairing attempt. Expired rows are removed when the next one starts (kept for 1 day)."""

    __tablename__ = "display_pairings"

    id: Mapped[int] = mapped_column(BigIntPk, primary_key=True, autoincrement=True)
    user_code_hash: Mapped[str] = mapped_column(sa.String(64), unique=True, nullable=False)
    device_code_hash: Mapped[str] = mapped_column(sa.String(64), unique=True, nullable=False)
    expires_at = mapped_column(sa.DateTime(), nullable=False, index=True)
    created_at = mapped_column(sa.DateTime(), nullable=False, default=utcnow)
    # Display account created on approval. NULL before approval. The row is not needed once the account is gone
    approved_account_id: Mapped[int | None] = mapped_column(
        BigIntPk, sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=True, index=True
    )
    approved_at = mapped_column(sa.DateTime(), nullable=True)
    claimed_at = mapped_column(sa.DateTime(), nullable=True)


class DisplayCredentialRecord(Base):
    """Device credential. One per display account; deleted along with the account."""

    __tablename__ = "display_credentials"

    account_id: Mapped[int] = mapped_column(BigIntPk, sa.ForeignKey("users.id", ondelete="CASCADE"), primary_key=True)
    credential_hash: Mapped[str] = mapped_column(sa.String(64), unique=True, nullable=False)
    created_at = mapped_column(sa.DateTime(), nullable=False, default=utcnow)
    last_used_at = mapped_column(sa.DateTime(), nullable=False, default=utcnow)


__all__ = ["DisplayCredentialRecord", "DisplayPairingRecord"]
