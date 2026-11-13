"""SQLAlchemy implementation of revocation records (ADR-0032)."""

from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy import delete, or_, select
from sqlalchemy.orm import Session
from sqlalchemy.sql.elements import ColumnElement

from bounded_contexts.identity_federation.domain.entities.session_revocation import (
    SessionRevocation,
)
from bounded_contexts.identity_federation.domain.value_objects.federated_login import (
    FederatedLogin,
)
from bounded_contexts.identity_federation.infrastructure.identity_federation_models import (
    FederatedSessionRevocationRecord,
)
from shared.kernel.timestamps import utcnow


@dataclass(frozen=True)
class SqlSessionRevocationRepository:
    session: Session

    def record(self, revocation: SessionRevocation) -> bool:
        """Keep a record. If the same ``jti`` already exists, ``False`` (ignored as a resend)."""
        self.session.execute(
            delete(FederatedSessionRevocationRecord).where(FederatedSessionRevocationRecord.expires_at < utcnow())
        )
        if self.session.get(FederatedSessionRevocationRecord, revocation.jti) is not None:
            return False
        self.session.add(
            FederatedSessionRevocationRecord(
                jti=revocation.jti,
                issuer=revocation.session.issuer,
                subject=revocation.session.subject,
                session_id=revocation.session.session_id,
                revoked_at=revocation.revoked_at,
                expires_at=revocation.expires_at,
            )
        )
        self.session.flush()
        return True

    def is_revoked(self, login: FederatedLogin) -> bool:
        """Whether there is a record invalidating the login.

        ⚠ **A row with NULL ``session_id`` is a per-user stop**, so it matches whatever
        ``session_id`` this side has. Conversely, when this side is ``None`` (an IdP that does not
        issue ``sid``), it only matches per-user rows.
        """
        record = FederatedSessionRevocationRecord
        target = login.session
        matches_session: ColumnElement[bool] = record.session_id.is_(None)
        if target.session_id is not None:
            matches_session = or_(matches_session, record.session_id == target.session_id)
        found = self.session.scalar(
            select(record.jti)
            .where(
                record.issuer == target.issuer,
                record.subject == target.subject,
                record.revoked_at >= login.started_at,
                matches_session,
            )
            .limit(1)
        )
        return found is not None


__all__ = ["SqlSessionRevocationRepository"]
