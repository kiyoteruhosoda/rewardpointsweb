"""Someone who already has an account joins a family with an invitation code.

Accepting can only join as a parent (ADR-0018).

- Only accounts that can be guardians (member role) may use a parent invitation.
  A child (guest) using one would become a guardian in name only, so we refuse.
  A child becomes an adult via independence (ADR-0014) or an admin role change.
- A child invitation can only be used when creating a new account (redeem —
  ADR-0011). Linking an existing account as a child would let the cleanup after
  removal (account deletion) take down an account that exists independently.
"""

from __future__ import annotations

from dataclasses import dataclass

from bounded_contexts.reward_points.application.dto.family_dto import RedeemedInvitationDTO
from bounded_contexts.reward_points.application.invitation_binder import InvitationBinder
from bounded_contexts.reward_points.domain.exceptions import (
    ChildInvitationRequiresSignupError,
    FamilyNotFoundError,
    GuardianAccountRequiredError,
)
from bounded_contexts.reward_points.domain.repositories.family_repository import IFamilyRepository


@dataclass(frozen=True, kw_only=True)
class AcceptInvitationCommand:
    code: str
    account_id: int
    username: str
    display_name: str | None
    # Whether the caller has the guardian scope (family:manage); verified in the Presentation layer
    can_guard: bool


class AcceptInvitationUseCase:
    def __init__(self, binder: InvitationBinder, families: IFamilyRepository) -> None:
        self._binder = binder
        self._families = families

    def execute(self, command: AcceptInvitationCommand) -> RedeemedInvitationDTO:
        membership = self._binder.bind(
            code=command.code,
            account_id=command.account_id,
            display_name=command.display_name,
        )
        # Rejecting here rolls back the whole transaction, so the invitation code is not consumed
        if membership.role.has_own_ledger:
            raise ChildInvitationRequiresSignupError
        if membership.role.is_guardian and not command.can_guard:
            raise GuardianAccountRequiredError
        family = self._families.find_by_id(membership.family_id)
        if family is None:
            raise FamilyNotFoundError
        return RedeemedInvitationDTO(
            family_id=family.id,
            family_name=family.name_value,
            membership_id=membership.id,
            role=membership.role,
            username=command.username,
        )


__all__ = ["AcceptInvitationCommand", "AcceptInvitationUseCase"]
