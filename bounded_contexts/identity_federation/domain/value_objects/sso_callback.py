"""The return from the IdP (``code`` / ``state`` and the passphrase the browser holds).

Completing a login and completing a link (ADR-0036) receive the same three, so they are grouped as a value.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class SsoCallback:
    code: str
    state: str
    #: The passphrase put into a cookie when sending the browser out. If absent, matching fails.
    browser_binding: str | None


__all__ = ["SsoCallback"]
