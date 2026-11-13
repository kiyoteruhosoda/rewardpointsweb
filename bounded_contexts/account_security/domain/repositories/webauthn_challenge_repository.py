"""Persistence interface for WebAuthn challenges (implemented in the infrastructure layer)."""

from __future__ import annotations

from typing import Protocol

from bounded_contexts.account_security.domain.entities.webauthn_challenge import (
    WebAuthnChallenge,
)


class WebAuthnChallengeRepository(Protocol):
    def issue(self, challenge: WebAuthnChallenge) -> WebAuthnChallenge:
        """Save a challenge. Clean up expired ones at the same time."""

    def consume(self, challenge_id: str, purpose: str) -> WebAuthnChallenge:
        """Take out a challenge and discard it (one-time).

        If not found, of a different purpose, or expired,
        :class:`~bounded_contexts.account_security.domain.exceptions.ChallengeNotFoundError`.
        """


__all__ = ["WebAuthnChallengeRepository"]
