"""Authenticated principal (the verified result passed to the Presentation layer).

Authorization is decided only by :meth:`can` (scope based). Role names are not kept
(see CLAUDE.md "Permission management").

``username`` is the login identifier, ``display_name`` is the name shown on screen, and
``email`` is optional (ADR-0011). The three are kept separately because some accounts
have no email address.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass, field


@dataclass(frozen=True)
class AuthenticatedPrincipal:
    user_id: int
    username: str
    display_name: str
    email: str | None = None
    permissions: frozenset[str] = field(default_factory=frozenset)
    # Logged in with a temporary password. No other action is allowed until it is changed
    must_change_password: bool = False
    # Whether this is a display device (signage) session (ADR-0047). Paths that change credentials are blocked
    via_display_device: bool = False

    @property
    def id_hash(self) -> str:
        """User identifier for logs (a hash so no PII is kept)."""
        return hashlib.sha256(str(self.user_id).encode()).hexdigest()[:16]

    def can(self, *codes: str) -> bool:
        """Whether **all** of the given permission codes are held."""
        return all(code in self.permissions for code in codes)


__all__ = ["AuthenticatedPrincipal"]
