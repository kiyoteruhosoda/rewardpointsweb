"""Count, per user, "the authentication methods this app holds" (ADR-0035).

This context answers **only for what it holds itself** -- two-factor authentication (TOTP) and
passkeys. The password is a column of ``users`` and so belongs to shared; entrances via the IdP
are answered by the identity federation context.
"""

from __future__ import annotations

from dataclasses import dataclass

from bounded_contexts.account_security.domain.repositories.local_factor_directory import (
    LocalFactorDirectory,
)
from bounded_contexts.account_security.domain.value_objects.local_factors import (
    LocalFactors,
)


@dataclass(frozen=True)
class CountLocalFactors:
    directory: LocalFactorDirectory

    def execute(self) -> dict[int, LocalFactors]:
        return self.directory.factors_by_user()

    def for_user(self, user_id: int) -> LocalFactors:
        """For one user only. Used when the target is fixed, like one's own settings screen (ADR-0036)."""
        return self.directory.factors_of(user_id)


__all__ = ["CountLocalFactors"]
