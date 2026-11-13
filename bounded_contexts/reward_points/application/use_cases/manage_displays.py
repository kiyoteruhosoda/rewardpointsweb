"""Attach, detach and list display devices for families (operators; ADR-0047).

Calls reaching here are limited to people holding ``display:approve`` (operators) or the
device itself re-fetching its session (``/api/display/session``).

⚠ **A device can be attached only when the approver is an owner / parent of that family**
(task #758). It used to pass on the scope alone, so operators could show any family's
ledger on a device, and an admin could reach every family's ledger by granting themselves
operator. The selectable families are narrowed by the same condition.

The path for detaching from the family side (a parent removing it on the family screen)
belongs to :class:`RemoveMembershipUseCase`.
"""

from __future__ import annotations

from dataclasses import dataclass

from bounded_contexts.reward_points.application.dto.display_dto import DisplayableFamilyDTO, DisplayDTO
from bounded_contexts.reward_points.domain.entities.family import Family
from bounded_contexts.reward_points.domain.entities.family_membership import FamilyMembership
from bounded_contexts.reward_points.domain.exceptions import (
    DisplayNotFoundError,
    FamilyAccessDeniedError,
    FamilyNotFoundError,
)
from bounded_contexts.reward_points.domain.repositories.account_directory import IAccountProvisioning
from bounded_contexts.reward_points.domain.repositories.family_membership_repository import (
    IFamilyMembershipRepository,
)
from bounded_contexts.reward_points.domain.repositories.family_repository import IFamilyRepository
from bounded_contexts.reward_points.domain.value_objects.display_name import DisplayName
from bounded_contexts.reward_points.domain.value_objects.family_role import FamilyRole


@dataclass(frozen=True, kw_only=True)
class AttachDisplayCommand:
    family_id: int
    #: The approver. Rejected unless an owner / parent of the family to display
    approver_id: int
    #: Device name (e.g. "Living room")
    name: str


class DisplayRoster:
    """Roster of display devices. Handles attach, detach, lookup and listing together."""

    def __init__(
        self,
        *,
        families: IFamilyRepository,
        memberships: IFamilyMembershipRepository,
        provisioning: IAccountProvisioning,
    ) -> None:
        self._families = families
        self._memberships = memberships
        self._provisioning = provisioning

    def attach(self, command: AttachDisplayCommand) -> DisplayDTO:
        """Create a display account and add it to the family as a display device.

        :class:`FamilyAccessDeniedError` unless the approver is a parent of the family. Whether
        the family exists is checked afterwards (so nobody can probe the existence of
        families they do not belong to).
        """
        approver = self._memberships.find_in_family(family_id=command.family_id, account_id=command.approver_id)
        if approver is None or not approver.role.is_guardian:
            raise FamilyAccessDeniedError
        family = self._families.find_by_id(command.family_id)
        if family is None:
            raise FamilyNotFoundError
        name = DisplayName(command.name.strip()).value
        account = self._provisioning.create_display_account(display_name=name)
        membership = self._memberships.add(
            family_id=family.id,
            account_id=account.account_id,
            role=FamilyRole.DISPLAY,
            display_name=name,
        )
        return _to_dto(membership, family)

    def detach(self, account_id: int) -> DisplayDTO:
        """Detach a display device. Deletes both the membership and the account (1 device = 1 account)."""
        found = self.find(account_id)
        if found is None:
            raise DisplayNotFoundError
        self._memberships.delete(found.membership_id)
        self._provisioning.delete_account(account_id)
        return found

    def find(self, account_id: int) -> DisplayDTO | None:
        """The device, if *account_id* is attached to a family as a display device."""
        membership = next((m for m in self._memberships.list_for_account(account_id) if m.role.is_display), None)
        if membership is None:
            return None
        family = self._families.find_by_id(membership.family_id)
        return None if family is None else _to_dto(membership, family)

    def list_all(self) -> list[DisplayDTO]:
        displays = self._memberships.list_displays()
        families = {family.id: family for family in self._families.list_by_ids([d.family_id for d in displays])}
        return [_to_dto(display, families[display.family_id]) for display in displays if display.family_id in families]

    def families_to_display(self, approver_id: int) -> list[DisplayableFamilyDTO]:
        """Only families *approver_id* belongs to as owner / parent (same condition as :meth:`attach`)."""
        family_ids = [m.family_id for m in self._memberships.list_for_account(approver_id) if m.role.is_guardian]
        return [
            DisplayableFamilyDTO(id=family.id, name=family.name_value)
            for family in self._families.list_by_ids(family_ids)
        ]


def _to_dto(membership: FamilyMembership, family: Family) -> DisplayDTO:
    if membership.account_id is None:  # A display device is linked to an account at approval time
        raise DisplayNotFoundError
    return DisplayDTO(
        account_id=membership.account_id,
        membership_id=membership.id,
        family_id=family.id,
        family_name=family.name_value,
        name=membership.display_name_value,
        created_at=membership.created_at,
    )


__all__ = ["AttachDisplayCommand", "DisplayRoster"]
