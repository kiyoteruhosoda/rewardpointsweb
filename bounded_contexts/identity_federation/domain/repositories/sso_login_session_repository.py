"""認可要求の控えの永続化インターフェース（実装は Infrastructure 層）。"""

from __future__ import annotations

from typing import Protocol

from bounded_contexts.identity_federation.domain.entities.sso_login_session import (
    SsoLoginSession,
)


class SsoLoginSessionRepository(Protocol):
    def issue(self, session: SsoLoginSession) -> SsoLoginSession:
        """控えを保存する。期限切れのものはこの機会に掃除する。"""

    def consume(self, state: str) -> SsoLoginSession:
        """控えを取り出して破棄する（1 回限り）。

        見つからない・期限切れの場合は
        :class:`~bounded_contexts.identity_federation.domain.exceptions.SsoLoginSessionNotFoundError`。
        """


__all__ = ["SsoLoginSessionRepository"]
