"""Ports for looking up / creating accounts.

Accounts themselves are not owned by this context, so only the needed parts are carved
out. Reading (:class:`IAccountDirectory`) and writing (:class:`IAccountProvisioning`) are
separate because only paths that create accounts, such as accepting an invitation, need
the latter.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import datetime

from bounded_contexts.reward_points.domain.value_objects.family_role import FamilyRole


@dataclass(frozen=True, kw_only=True)
class AccountRef:
    """The minimum needed to display a member (not used for authorization)."""

    account_id: int
    username: str
    display_name: str
    # Email is optional (ADR-0011). Some accounts have none
    email: str | None


@dataclass(frozen=True, kw_only=True)
class TemporaryPassword:
    """A temporary password issued by a parent. The plaintext can be retrieved only this once."""

    password: str
    expires_at: datetime


class IAccountDirectory(ABC):
    @abstractmethod
    def describe(self, account_ids: Sequence[int]) -> Mapping[int, AccountRef]:
        """Account ID -> display info. IDs not found are omitted from the result."""


class IAccountProvisioning(ABC):
    @abstractmethod
    def is_username_taken(self, username: str) -> bool: ...

    @abstractmethod
    def create_account(
        self, *, username: str, password: str, role: FamilyRole, display_name: str | None = None
    ) -> AccountRef:
        """Create an account on accepting an invitation.

        No email address is taken. Child accounts are assumed to have no email address
        (ADR-0011). The implementation decides the application role to grant from *role*.

        *display_name* is the name the person goes by. If omitted or empty, the login
        identifier becomes the display name. This differs from the name used within the
        family (the membership's display_name); it is the account's own display name
        (ADR-0010).
        """

    @abstractmethod
    def create_display_account(self, *, display_name: str) -> AccountRef:
        """Create a display device account (ADR-0047).

        It has no password or email address. The only way in is the paired device, and
        nobody types the login identifier, so the implementation decides it.
        """

    @abstractmethod
    def issue_temporary_password(self, account_id: int) -> TemporaryPassword:
        """Issue a temporary password and require a change after the next login."""

    @abstractmethod
    def grant_guardian_permissions(self, account_id: int) -> None:
        """Give the account the same application role as a parent (member).

        With the child role one can neither create a family nor record points, so this is
        called when independence is established (ADR-0014). If the account already holds
        every guardian-level scope, its roles are left untouched.
        """

    @abstractmethod
    def delete_account(self, account_id: int) -> None:
        """Delete the account of a removed child or detached display device (ADR-0018, ADR-0047).

        Child accounts are born from accepting an invitation and exist only as family
        memberships. Once removal (only when the ledger is empty — ADR-0013) cuts the tie to
        the family, the account is not kept either.
        """


__all__ = ["AccountRef", "IAccountDirectory", "IAccountProvisioning", "TemporaryPassword"]
