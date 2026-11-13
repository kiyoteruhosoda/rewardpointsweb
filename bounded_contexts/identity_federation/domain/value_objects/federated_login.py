"""One session of this app that started via the IdP (ADR-0032).

The address (:class:`FederatedSession`) plus **when it started**. Revocation records work in the form
"invalidate sessions that started before this time", so the time is needed.

⚠ **It is the time the session started, not the time the token was issued.** Renewing it on every
refresh would let **a single refresh slip past the revocation** (the ``iat`` of a refreshed token
is always later than the revocation).

⚠ **The token's ``iat`` cannot be used instead.** ``iat`` has only second precision, so it would
catch a user who signed in again in the same second right after the stop.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from bounded_contexts.identity_federation.domain.value_objects.federated_session import (
    FederatedSession,
)


@dataclass(frozen=True)
class FederatedLogin:
    session: FederatedSession
    started_at: datetime


__all__ = ["FederatedLogin"]
