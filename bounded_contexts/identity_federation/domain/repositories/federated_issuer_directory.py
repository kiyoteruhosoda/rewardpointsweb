"""Interface for the link inventory (implemented in the Infrastructure layer; ADR-0035)."""

from __future__ import annotations

from typing import Protocol


class FederatedIssuerDirectory(Protocol):
    def issuers_by_user(self) -> dict[int, tuple[str, ...]]:
        """User ID → list of linked issuers. Users with none are omitted.

        ⚠ **Returns everyone at once.** A one-user-at-a-time lookup would make the screen
        issue as many queries as there are users.
        """


__all__ = ["FederatedIssuerDirectory"]
