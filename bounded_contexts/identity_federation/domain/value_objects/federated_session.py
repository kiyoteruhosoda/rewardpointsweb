"""The address of one login session on the IdP side (ADR-0032).

``(issuer, subject)`` is "who", and ``session_id`` (the ID token's ``sid``) is
"which login". Revocation propagation arrives addressed by this triple -- if ``sid`` is
known, **only that device's session** can be dropped.

``session_id`` is ``None`` in two cases.

- **The IdP does not issue ``sid``.** Then revocation can only be per user.
- **The revocation notice has no ``sid``** (the whole user was stopped). Then
  **all** of that user's sessions are dropped.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class FederatedSession:
    issuer: str
    subject: str
    session_id: str | None = None


__all__ = ["FederatedSession"]
