"""Interface for the second-factor inventory (implemented in the infrastructure layer. ADR-0035)."""

from __future__ import annotations

from typing import Protocol

from bounded_contexts.account_security.domain.value_objects.local_factors import (
    LocalFactors,
)


class LocalFactorDirectory(Protocol):
    def factors_by_user(self) -> dict[int, LocalFactors]:
        """User ID -> second factors. Users without any are not included.

        ⚠ **Return everyone at once.** Looking up one user at a time would make the screen
        issue as many queries as there are users.
        """

    def factors_of(self, user_id: int) -> LocalFactors:
        """Count for one user only. **Use only when the target is fixed to one person, like one's
        own settings screen** (do not call it from a list).
        """


__all__ = ["LocalFactorDirectory"]
