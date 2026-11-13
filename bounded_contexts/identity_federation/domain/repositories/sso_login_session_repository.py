"""Persistence interface for authorization request records (implemented in the Infrastructure layer)."""

from __future__ import annotations

from typing import Protocol

from bounded_contexts.identity_federation.domain.entities.sso_login_session import (
    SsoLoginSession,
)


class SsoLoginSessionRepository(Protocol):
    def issue(self, session: SsoLoginSession) -> SsoLoginSession:
        """Save a record. Expired ones are cleaned up at this opportunity."""

    def peek(self, state: str) -> SsoLoginSession | None:
        """Read a record **without deleting it**. ``None`` if absent or expired (ADR-0036).

        ⚠ **Do not authenticate with this.** It is used only to decide "is this a login return or a
        linking return"; passphrase matching and consumption are done by the following :meth:`consume`.
        """

    def consume(self, state: str) -> SsoLoginSession:
        """Take out a record and discard it (one time only).

        If not found or expired, raises
        :class:`~bounded_contexts.identity_federation.domain.exceptions.SsoLoginSessionNotFoundError`.
        """


__all__ = ["SsoLoginSessionRepository"]
