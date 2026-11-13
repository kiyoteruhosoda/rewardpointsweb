"""SQLAlchemy implementation of authorization request records."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, cast

from sqlalchemy import delete
from sqlalchemy.engine import CursorResult
from sqlalchemy.orm import Session

from bounded_contexts.identity_federation.domain.entities.sso_login_session import (
    SsoLoginSession,
)
from bounded_contexts.identity_federation.domain.exceptions import (
    SsoLoginSessionNotFoundError,
)
from bounded_contexts.identity_federation.infrastructure.identity_federation_models import (
    SsoLoginSessionRecord,
)
from shared.kernel.timestamps import utcnow


@dataclass(frozen=True)
class SqlSsoLoginSessionRepository:
    session: Session

    def issue(self, session: SsoLoginSession) -> SsoLoginSession:
        # Records that never came back (the user closed the IdP screen, etc.) would keep
        # piling up if left alone. Expired ones are cleaned up on every issue.
        self.session.execute(delete(SsoLoginSessionRecord).where(SsoLoginSessionRecord.expires_at < utcnow()))
        self.session.add(
            SsoLoginSessionRecord(
                state=session.state,
                nonce=session.nonce,
                code_verifier=session.code_verifier,
                binding_hash=session.binding_hash,
                redirect_to=session.redirect_to,
                expires_at=session.expires_at,
                link_user_id=session.link_user_id,
                silent=session.silent,
                renewal=session.renewal,
            )
        )
        self.session.flush()
        return session

    def peek(self, state: str) -> SsoLoginSession | None:
        """Read a record **without deleting it** (ADR-0036). Expired ones are treated as absent."""
        record = self.session.get(SsoLoginSessionRecord, state)
        if record is None:
            return None
        found = _to_session(record)
        return None if found.is_expired(utcnow()) else found

    def consume(self, state: str) -> SsoLoginSession:
        record = self.session.get(SsoLoginSessionRecord, state)
        if record is None:
            raise SsoLoginSessionNotFoundError

        consumed = _to_session(record)

        # Consumption is decided by **whether the delete succeeded** ("read then delete" would let
        # two concurrent requests with the same ``state`` both finish reading). DELETE takes a row
        # lock, so the later one waits for the earlier commit and then returns 0 rows.
        result = cast(
            "CursorResult[Any]",
            self.session.execute(
                delete(SsoLoginSessionRecord).where(SsoLoginSessionRecord.state == state),
                execution_options={"synchronize_session": False},
            ),
        )
        self.session.expunge(record)
        if result.rowcount != 1:
            raise SsoLoginSessionNotFoundError
        if consumed.is_expired(utcnow()):
            raise SsoLoginSessionNotFoundError
        return consumed


def _to_session(record: SsoLoginSessionRecord) -> SsoLoginSession:
    return SsoLoginSession(
        state=record.state,
        nonce=record.nonce,
        code_verifier=record.code_verifier,
        binding_hash=record.binding_hash,
        redirect_to=record.redirect_to,
        expires_at=record.expires_at,
        link_user_id=record.link_user_id,
        silent=record.silent,
        renewal=record.renewal,
    )


__all__ = ["SqlSsoLoginSessionRepository"]
