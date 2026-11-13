"""Persistence interface for exchange tickets (implemented in the Infrastructure layer)."""

from __future__ import annotations

from typing import Protocol

from bounded_contexts.identity_federation.domain.entities.sso_login_ticket import (
    SsoLoginTicket,
)


class SsoLoginTicketRepository(Protocol):
    def issue(self, ticket: SsoLoginTicket) -> SsoLoginTicket:
        """Save a ticket. Expired ones are cleaned up at this opportunity."""

    def redeem(self, ticket_hash: str) -> SsoLoginTicket:
        """Take out a ticket and discard it (one time only).

        If not found or expired, raises
        :class:`~bounded_contexts.identity_federation.domain.exceptions.SsoTicketNotFoundError`.
        """


__all__ = ["SsoLoginTicketRepository"]
