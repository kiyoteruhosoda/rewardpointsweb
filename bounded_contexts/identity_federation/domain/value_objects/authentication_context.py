"""Matching the requested authentication strength (``acr_values``) against the returned ``acr``.

**If you request it, verify it; otherwise do not request it** (ADR-0039). Merely sending
``acr_values`` guarantees nothing -- a single misspelling in the IdP-side policy drops the
condition and single-factor logins pass silently. The only way the RP can notice is to match the
returned ``acr`` against the request.

⚠ **``amr`` is not used.** RFC 8176 ``amr`` is a list of methods used, not a strength.
Via an external IdP (``fed``), the IdP itself does not know what was used beyond it, so
whether it was multi-factor cannot be read from the list of values.
"""

from __future__ import annotations

from dataclasses import dataclass

from bounded_contexts.identity_federation.domain.exceptions import (
    SsoAcrNotSatisfiedError,
)


@dataclass(frozen=True)
class RequestedAuthenticationContext:
    #: Candidate ``acr`` values to request. **Empty = not requested** (default).
    values: tuple[str, ...] = ()

    @property
    def is_requested(self) -> bool:
        return bool(self.values)

    def ensure_satisfied(self, acr: object) -> None:
        """Check that the returned ``acr`` matches one of the requested values.

        ⚠ **Also refuse when no ``acr`` is returned.** Having requested it without getting the
        guarantee, it must not pass. Connecting to an IdP without reserved values keeps working as
        before by not requesting at all (empty ``values``).
        """
        if not self.is_requested:
            return
        if not isinstance(acr, str) or acr not in self.values:
            raise SsoAcrNotSatisfiedError


__all__ = ["RequestedAuthenticationContext"]
