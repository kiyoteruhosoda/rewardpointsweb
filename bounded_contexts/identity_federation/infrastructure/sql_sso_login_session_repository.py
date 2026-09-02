"""認可要求の控えの SQLAlchemy 実装。"""

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
        # 戻ってこなかった控え（利用者が IdP の画面を閉じた等）は放っておくと
        # 溜まり続ける。発行のたびに期限切れを掃除する。
        self.session.execute(delete(SsoLoginSessionRecord).where(SsoLoginSessionRecord.expires_at < utcnow()))
        self.session.add(
            SsoLoginSessionRecord(
                state=session.state,
                nonce=session.nonce,
                code_verifier=session.code_verifier,
                binding_hash=session.binding_hash,
                redirect_to=session.redirect_to,
                expires_at=session.expires_at,
            )
        )
        self.session.flush()
        return session

    def consume(self, state: str) -> SsoLoginSession:
        record = self.session.get(SsoLoginSessionRecord, state)
        if record is None:
            raise SsoLoginSessionNotFoundError

        consumed = SsoLoginSession(
            state=record.state,
            nonce=record.nonce,
            code_verifier=record.code_verifier,
            binding_hash=record.binding_hash,
            redirect_to=record.redirect_to,
            expires_at=record.expires_at,
        )

        # 消費は**削除の成否**で決める（「読んでから消す」だと同じ ``state`` を
        # 同時に 2 本送られたとき両方が読み終えてしまう）。DELETE は行ロックを
        # 取るため、後続は先行のコミットを待ってから 0 行を返す。
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


__all__ = ["SqlSsoLoginSessionRepository"]
