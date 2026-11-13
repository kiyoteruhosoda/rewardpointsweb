"""Create an account with an invitation code and join the family right away
(callable without authentication).

This is the only way to create a child account. A child cannot create one alone;
it works only when a parent has created the membership and handed over an
invitation code (ADR-0011). No email address is accepted.

The new account is not signed in. The caller (the screen) signs in as usual with
the chosen ``username`` and password.

⚠ **When an IdP (SSO) is configured, parent invitations cannot be used here**
(ADR-0048). An adult has exactly one account, created when they sign in through
the IdP, and a parent joins by accepting after signing in. Creating it here would
make a separate account without an email address and nothing to link it to the
IdP account, so the same person would end up with two accounts on their first
SSO sign-in.
"""

from __future__ import annotations

from dataclasses import dataclass

from bounded_contexts.reward_points.application.dto.family_dto import RedeemedInvitationDTO
from bounded_contexts.reward_points.application.invitation_binder import InvitationBinder
from bounded_contexts.reward_points.domain.exceptions import (
    FamilyNotFoundError,
    GuardianInvitationRequiresSignInError,
    InvitationNotFoundError,
    UsernameAlreadyTakenError,
)
from bounded_contexts.reward_points.domain.repositories.account_directory import IAccountProvisioning
from bounded_contexts.reward_points.domain.repositories.family_invitation_repository import (
    IFamilyInvitationRepository,
)
from bounded_contexts.reward_points.domain.repositories.family_repository import IFamilyRepository
from shared.kernel.timestamps import utcnow


@dataclass(frozen=True, kw_only=True)
class RedeemInvitationCommand:
    code: str
    username: str
    password: str
    display_name: str | None


class RedeemInvitationUseCase:
    def __init__(
        self,
        *,
        binder: InvitationBinder,
        invitations: IFamilyInvitationRepository,
        families: IFamilyRepository,
        provisioning: IAccountProvisioning,
        adults_sign_in_through_idp: bool,
    ) -> None:
        self._binder = binder
        self._invitations = invitations
        self._families = families
        self._provisioning = provisioning
        self._adults_sign_in_through_idp = adults_sign_in_through_idp

    def execute(self, command: RedeemInvitationCommand) -> RedeemedInvitationDTO:
        invitation = self._invitations.find_by_code(command.code)
        # Check the code before creating the account. Rejecting it afterwards would let
        # an invalid code use up a login ID
        if invitation is None or not invitation.is_usable_at(utcnow()):
            raise InvitationNotFoundError
        if invitation.role.is_guardian and self._adults_sign_in_through_idp:
            raise GuardianInvitationRequiresSignInError
        if self._provisioning.is_username_taken(command.username):
            raise UsernameAlreadyTakenError

        account = self._provisioning.create_account(
            username=command.username,
            password=command.password,
            role=invitation.role,
            # Also use the name the person gave as the account's display name. For an
            # invitation with a prepared membership, the in-family name stays as the
            # parent set it, so otherwise the entered name would be kept nowhere
            display_name=command.display_name,
        )
        membership = self._binder.bind(
            code=command.code,
            account_id=account.account_id,
            display_name=command.display_name,
        )
        family = self._families.find_by_id(membership.family_id)
        if family is None:
            raise FamilyNotFoundError
        return RedeemedInvitationDTO(
            family_id=family.id,
            family_name=family.name_value,
            membership_id=membership.id,
            role=membership.role,
            username=account.username,
        )


__all__ = ["RedeemInvitationCommand", "RedeemInvitationUseCase"]
