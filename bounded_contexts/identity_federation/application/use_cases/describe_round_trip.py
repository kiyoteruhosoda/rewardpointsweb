"""Answer whether a returned round trip is a "login", a "link", or one tried without showing a screen (ADR-0036, ADR-0052).

⚠ **This does not authenticate.** It only peeks at the saved request **without deleting it**, neither checking
nor consuming the passphrase -- it is a query only for deciding which completion to call.
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
        """For a link round trip, the user who started it; for a login round trip, ``None``."""
        session = self.sessions.peek(state)
        return None if session is None else session.link_user_id

    def silently_declined(self, *, state: str, browser_binding: str | None) -> str | None:
        """If a round trip tried without showing a screen came back as "not signed in", its destination (ADR-0052).

        For a normal round trip or one from another browser, ``None`` (treated as a failure as before).
        The saved request is not deleted (it expires; the IdP did not issue a code for this round trip).
        """
        session = self.sessions.peek(state)
        if session is None or not session.declined_silently(hash_secret(browser_binding or "")):
            return None
        return session.redirect_to

    def is_renewal(self, *, state: str, browser_binding: str | None) -> bool:
        """Whether this is a round trip back to the sending browser that continues an expired login (ADR-0058)."""
        session = self.sessions.peek(state)
        return session is not None and session.renewal_from(hash_secret(browser_binding or ""))


__all__ = ["DescribeRoundTrip"]
