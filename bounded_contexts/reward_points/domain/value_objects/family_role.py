"""Role within a family.

Authorization decisions use only the properties of this enum; callers never write
comparisons like ``role == "owner"`` (the ADR-0009 authorization table appears only here).

============ ============ ============ ============ ======= ==============
role         administer   create child add / spend  correct view
============ ============ ============ ============ ======= ==============
owner        yes          yes          all children yes     all children
parent       no           yes          all children yes     all children
child        no           no           no           no      own ledger only
display      no           no           no           no      all children
============ ============ ============ ============ ======= ==============

``display`` is not a person but a display device (signage; ADR-0047). Created by approval,
it only views the ledgers of all the family's children. It has no ledger and cannot be
handed out by invitation.
"""

from __future__ import annotations

from enum import Enum


class FamilyRole(Enum):
    OWNER = "owner"
    PARENT = "parent"
    CHILD = "child"
    DISPLAY = "display"

    @property
    def is_guardian(self) -> bool:
        """Whether this is a parent role (owner or parent). Only these two can handle children's ledgers."""
        return self in (FamilyRole.OWNER, FamilyRole.PARENT)

    @property
    def can_administer_family(self) -> bool:
        """Whether it can administer the family itself (name, removing members). Owner only."""
        return self is FamilyRole.OWNER

    @property
    def sees_every_ledger(self) -> bool:
        """Whether it can see every child's ledger in the family. Parents and display devices (ADR-0047)."""
        return self.is_guardian or self is FamilyRole.DISPLAY

    @property
    def is_display(self) -> bool:
        """Whether this is a display device rather than a person (ADR-0047). Not counted as a family member."""
        return self is FamilyRole.DISPLAY

    @property
    def has_own_ledger(self) -> bool:
        """Whether this role holds a point ledger one-to-one."""
        return self is FamilyRole.CHILD

    @property
    def is_invitable(self) -> bool:
        """Whether this role may be handed out with an invitation code.

        Owner cannot. Otherwise the recipient could remove the original owner and take over
        the family (invitation acceptance also comes from unauthenticated paths). If the owner
        ever needs to be transferred, design a dedicated hand-over operation.

        Display devices cannot either. Devices are created only by operator approval (ADR-0047).
        """
        return self in (FamilyRole.PARENT, FamilyRole.CHILD)


__all__ = ["FamilyRole"]
