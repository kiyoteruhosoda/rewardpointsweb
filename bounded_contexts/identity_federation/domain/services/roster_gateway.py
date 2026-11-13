"""Gateway that looks up the assay roster (ADR-0040; implemented in the Infrastructure layer).

⚠ **Do not represent a failed lookup as "empty".** The implementation reports failure with
:class:`~bounded_contexts.identity_federation.domain.exceptions.IdentityProviderUnavailableError`
and the caller skips reconciliation altogether -- if it were indistinguishable from empty, merely assay
misbehaving would stop everyone.

⚠ When **this service account is not yet bound as the application's identity**, it reports
:class:`~bounded_contexts.identity_federation.domain.exceptions.MachineNotBoundToApplicationError`
separately (waiting for setup, not an outage). Nothing is changed in that case either.
"""

from __future__ import annotations

from typing import Protocol

from bounded_contexts.identity_federation.domain.value_objects.roster import Roster


class RosterGateway(Protocol):
    def fetch(self, *, subjects: tuple[str, ...]) -> Roster:
        """Look up the status of each of *subjects* (assay decides which application's roster it is from the
        service account presented).

        ⚠ **Ask by name.** ``unknown`` (= not present over there) is returned only in this form;
        listing candidates cannot tell you who "disappeared".
        """


__all__ = ["RosterGateway"]
