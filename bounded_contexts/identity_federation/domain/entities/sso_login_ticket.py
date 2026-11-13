"""One-time exchange ticket issued by the callback.

The return from the IdP is a browser **navigation**, and the SPA's JavaScript cannot read the response body.
Putting tokens in the URL would leave them in history, Referer and access logs, so instead only a short-lived
exchange ticket is handed over, and the SPA exchanges it for tokens with ``POST /api/auth/sso/token``
(ADR-0029).

The ticket itself is a credential handed to its holder, so only its hash is stored in the DB
(same treatment as password reset tokens).
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from bounded_contexts.identity_federation.domain.value_objects.federated_login import (
    FederatedLogin,
)


@dataclass(frozen=True)
class SsoLoginTicket:
    ticket_hash: str
    user_id: int
    redirect_to: str
    expires_at: datetime
    #: Which IdP session the login started from (ADR-0032). Unless it travels with the ticket,
    #: there is no way to decide whom to drop when a revocation notice arrives.
    login: FederatedLogin

    def is_expired(self, now: datetime) -> bool:
        return now >= self.expires_at


__all__ = ["SsoLoginTicket"]
