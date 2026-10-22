"""戻ってきた往復が「ログイン」か「連携」か、画面を出さずに試した往復か（ADR-0036・ADR-0052）を答える。

⚠ **これで認証しない。** 控えを**消さずに**覗くだけで、合言葉の照合も消費も
しない ——どちらの後始末を呼ぶかを決めるためだけの問い合わせである。
"""

from __future__ import annotations

from dataclasses import dataclass

from bounded_contexts.identity_federation.domain.repositories.sso_login_session_repository import (
    SsoLoginSessionRepository,
)
from bounded_contexts.identity_federation.domain.services.login_secrets import hash_secret


@dataclass(frozen=True)
class DescribeRoundTrip:
    sessions: SsoLoginSessionRepository

    def execute(self, *, state: str) -> int | None:
        """連携の往復ならそれを始めた利用者、ログインの往復なら ``None``。"""
        session = self.sessions.peek(state)
        return None if session is None else session.link_user_id

    def silently_declined(self, *, state: str, browser_binding: str | None) -> str | None:
        """画面を出さずに試した往復が「入っていない」で戻ったなら、その行き先（ADR-0052）。

        ふつうの往復・別のブラウザの往復なら ``None``（今までどおり失敗として扱う）。
        控えは消さない（期限で消える。この往復の code は IdP が出していない）。
        """
        session = self.sessions.peek(state)
        if session is None or not session.declined_silently(hash_secret(browser_binding or "")):
            return None
        return session.redirect_to


__all__ = ["DescribeRoundTrip"]
