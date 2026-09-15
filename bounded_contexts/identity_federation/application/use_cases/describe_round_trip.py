"""戻ってきた往復が「ログイン」か「連携」かを答える（ADR-0036）。

⚠ **これで認証しない。** 控えを**消さずに**覗くだけで、合言葉の照合も消費も
しない ——どちらの後始末を呼ぶかを決めるためだけの問い合わせである。
"""

from __future__ import annotations

from dataclasses import dataclass

from bounded_contexts.identity_federation.domain.repositories.sso_login_session_repository import (
    SsoLoginSessionRepository,
)


@dataclass(frozen=True)
class DescribeRoundTrip:
    sessions: SsoLoginSessionRepository

    def execute(self, *, state: str) -> int | None:
        """連携の往復ならそれを始めた利用者、ログインの往復なら ``None``。"""
        session = self.sessions.peek(state)
        return None if session is None else session.link_user_id


__all__ = ["DescribeRoundTrip"]
