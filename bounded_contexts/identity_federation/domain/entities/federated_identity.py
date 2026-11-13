"""Link between an external IdP account and a user of this app.

The key is ``(issuer, subject)``. The email address can change, so it is not the key.
So that one user can have multiple IdPs, there is no unique constraint on the user side.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime


@dataclass(frozen=True)
class FederatedIdentity:
    issuer: str
    subject: str
    user_id: int
    #: When it was linked. Set only when a stored row is loaded (for display on screen).
    linked_at: datetime | None = None
    #: When the user last signed in via SSO. Set only when a stored row is loaded.
    #: Used by periodic reconciliation to decide "which login the revocation applies to" (ADR-0040).
    last_login_at: datetime | None = None


__all__ = ["FederatedIdentity"]
