"""Output DTOs for families, members and invitations.

``role`` carries the domain enum as-is. Lowering it to a string would require converting
back to ``Literal["owner", "parent", "child"]`` in the Presentation layer, defeating type
checking. The enum values (``"owner"`` etc.) appear in the JSON.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from bounded_contexts.reward_points.application.dto.daily_bonus_dto import DailyBonusDTO
from bounded_contexts.reward_points.domain.entities.family import Family
from bounded_contexts.reward_points.domain.entities.family_membership import FamilyMembership
from bounded_contexts.reward_points.domain.value_objects.family_role import FamilyRole


@dataclass(frozen=True, kw_only=True)
class FamilySummaryDTO:
    id: int
    name: str
    my_membership_id: int
    my_role: FamilyRole
    member_count: int


@dataclass(frozen=True, kw_only=True)
class MembershipDTO:
    id: int
    display_name: str
    role: FamilyRole
    # A member not linked to an account cannot log in until given an invitation code
    is_linked: bool
    is_me: bool
    username: str | None
    # Only role = child has a ledger
    ledger_id: int | None
    balance: int | None
    # Whether independence was requested and awaits the child's own approval (ADR-0014)
    independence_proposed: bool = False
    # Daily bonus settings (ADR-0024). They appear in the family settings, so they ride on
    # the member (ADR-0027). ``None`` for members whose ledger is not visible. The default is
    # ``None`` for the same reason as ``can_*`` — responses returning a single member do not
    # read the ledger
    daily_bonus: DailyBonusDTO | None = None
    # Operations the viewer may perform on this member. The UI shows operations based on
    # these alone (same idea as the ledger's ``can_modify`` — never offer an operation that
    # is refused after pressing it). All default to false. Responses that just create and
    # return one member (adding a child, requesting independence) do not re-read the whole
    # family, so they are in no position to answer.
    can_reset_password: bool = False
    can_propose_independence: bool = False
    can_remove: bool = False


@dataclass(frozen=True, kw_only=True)
class FamilyDetailDTO:
    id: int
    name: str
    # Rules agreed in the family (ADR-0027). ``None`` if not written yet
    rules: str | None
    my_membership_id: int
    my_role: FamilyRole
    memberships: tuple[MembershipDTO, ...]


def detail_of(
    family: Family,
    *,
    viewer: FamilyMembership,
    memberships: tuple[MembershipDTO, ...],
) -> FamilyDetailDTO:
    """Build the family details.

    Five entry points return a family (create, view, rename, reorder, rewrite rules).
    They all return the same shape, so assembly lives here to avoid missing one when a
    field is added.
    """
    return FamilyDetailDTO(
        id=family.id,
        name=family.name_value,
        rules=family.rules_value,
        my_membership_id=viewer.id,
        my_role=viewer.role,
        memberships=memberships,
    )


@dataclass(frozen=True, kw_only=True)
class InvitationDTO:
    id: int
    role: FamilyRole
    target_membership_id: int | None
    target_display_name: str | None
    expires_at: datetime
    # The plaintext code is only included in the issuing response (only the hash is stored)
    code: str | None


@dataclass(frozen=True, kw_only=True)
class TemporaryPasswordDTO:
    membership_id: int
    username: str
    password: str
    expires_at: datetime
    # Returned so the issuance can be logged (not included in the response body)
    issued_by_membership_id: int


@dataclass(frozen=True, kw_only=True)
class RedeemedInvitationDTO:
    family_id: int
    family_name: str
    membership_id: int
    role: FamilyRole
    username: str


__all__ = [
    "FamilyDetailDTO",
    "FamilySummaryDTO",
    "InvitationDTO",
    "MembershipDTO",
    "RedeemedInvitationDTO",
    "TemporaryPasswordDTO",
    "detail_of",
]
