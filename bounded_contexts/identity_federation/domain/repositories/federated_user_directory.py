"""Gateway to users (``users``).

From identity federation's point of view, looking up users is an "external system". So that the Domain
layer does not touch SQLAlchemy models, only the needed operations are declared here, and the
implementation (Infrastructure layer) bridges to the ``shared`` models.

**The only thing it creates is an account for a first-time user** (ADR-0041). Who may get one is decided by
assay's application assignments; this side merely welcomes whoever comes back holding a code.
"""

from __future__ import annotations

from typing import Protocol

from bounded_contexts.identity_federation.domain.entities.federated_account import (
    FederatedAccount,
)


class FederatedUserDirectory(Protocol):
    def find_by_id(self, user_id: int) -> FederatedAccount | None:
        """Look up a user by internal ID. ``None`` if absent."""

    def find_by_email(self, email: str) -> FederatedAccount | None:
        """Look up a user by email address (a hint for the first link).

        Email is optional, so users without one never match
        (ADR-0011). For accounts whose identifier is an email address, the caller
        also searches with ``find_by_username``.
        """

    def find_by_username(self, username: str) -> FederatedAccount | None:
        """Look up a user by login identifier (pass the normalized value). ``None`` if absent."""

    def provision(self, *, username: str, email: str | None, display_name: str) -> FederatedAccount | None:
        """Create an account for a first-time user (ADR-0041).

        The account gets the same defaults as one created in the admin screen: **parent (``member``), no family**
        (ADR-0018). ⚠ **It has no local password** (NULL per ADR-0034)
        -- the only way in is the IdP.

        ⚠ **If a unique column collides, create nothing and return ``None``.** Even if checked just before,
        two concurrent round trips of the same person returning can overtake each other.
        """

    def refresh_profile(self, user_id: int, *, email: str | None, display_name: str) -> None:
        """Overwrite the copy with the name and email address the IdP asserted (ADR-0038).

        ⚠ **The IdP is the source of truth for the copy** (idp ADR-0049 I5). Without writing it,
        a rename or email change over there would leave **the display here stale forever**.

        ⚠ **Do not write a value that collides with another user.** ``users.email`` is unique, so
        writing a colliding value would **make login fail with 500** -- updating the copy must not
        break login, so just that field is silently skipped.

        ⚠ **Do not clear fields that were not asserted.** ``email`` being ``None`` means
        "unknown this time", not "please empty it" (this also avoids breaking users without an
        email address, per ADR-0011).
        """


__all__ = ["FederatedUserDirectory"]
