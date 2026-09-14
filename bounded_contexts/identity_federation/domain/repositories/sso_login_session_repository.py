"""認可要求の控えの永続化インターフェース（実装は Infrastructure 層）。"""

from __future__ import annotations

from typing import Protocol

from bounded_contexts.identity_federation.domain.entities.sso_login_session import (
    SsoLoginSession,
)


class SsoLoginSessionRepository(Protocol):
    def issue(self, session: SsoLoginSession) -> SsoLoginSession:
        """控えを保存する。期限切れのものはこの機会に掃除する。"""

    def peek(self, state: str) -> SsoLoginSession | None:
        """控えを**消さずに**読む。無い・期限切れなら ``None``（ADR-0036）。

        ⚠ **これで認証しない。** 使うのは「ログインの戻りか、連携の戻りか」を
        決めるためだけで、合言葉の照合と消費は続く :meth:`consume` が行う。
        """

    def consume(self, state: str) -> SsoLoginSession:
        """控えを取り出して破棄する（1 回限り）。

        見つからない・期限切れの場合は
        :class:`~bounded_contexts.identity_federation.domain.exceptions.SsoLoginSessionNotFoundError`。
        """


__all__ = ["SsoLoginSessionRepository"]
