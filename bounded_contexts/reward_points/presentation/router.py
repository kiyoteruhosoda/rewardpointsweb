"""API of the reward_points context.

Authorization has two stages.

1. **scope** (``family:view`` / ``point:manage`` etc.) — may the caller perform the operation
2. **role within the family** (owner / parent / child) — may the caller touch *that*
   family / ledger

Stage 1 is declared here; stage 2 is decided by the Application layer's
:class:`~bounded_contexts.reward_points.application.family_access_resolver.FamilyAccessResolver`.
Even a user holding ``point:manage`` cannot touch a family they do not belong to.

Only invitation redemption (``/invitations/redeem``) can be called **unauthenticated**,
because the child has no account yet (ADR-0011).
"""

from __future__ import annotations

import logging
from typing import Annotated

from fastapi import APIRouter, Depends, status

from bounded_contexts.reward_points.application.dto.daily_bonus_dto import DailyBonusDTO
from bounded_contexts.reward_points.application.dto.family_dto import (
    FamilyDetailDTO,
    InvitationDTO,
    MembershipDTO,
    RedeemedInvitationDTO,
)
from bounded_contexts.reward_points.application.dto.ledger_dto import CorrectionDTO, TransactionDTO
from bounded_contexts.reward_points.application.dto.reward_event_dto import RewardEventDTO
from bounded_contexts.reward_points.application.use_cases.accept_invitation import AcceptInvitationCommand
from bounded_contexts.reward_points.application.use_cases.add_child_membership import (
    AddChildMembershipCommand,
)
from bounded_contexts.reward_points.application.use_cases.configure_daily_bonus import (
    ConfigureDailyBonusCommand,
)
from bounded_contexts.reward_points.application.use_cases.correct_point_transaction import (
    CorrectTransactionCommand,
)
from bounded_contexts.reward_points.application.use_cases.create_family import CreateFamilyCommand
from bounded_contexts.reward_points.application.use_cases.import_family import ImportFamilyCommand
from bounded_contexts.reward_points.application.use_cases.issue_invitation import IssueInvitationCommand
from bounded_contexts.reward_points.application.use_cases.manage_reward_events import (
    ChangeDeadlineCommand,
    CreateRewardEventCommand,
    StickerCommand,
)
from bounded_contexts.reward_points.application.use_cases.record_point_transaction import (
    RecordTransactionCommand,
)
from bounded_contexts.reward_points.application.use_cases.redeem_invitation import RedeemInvitationCommand
from bounded_contexts.reward_points.application.use_cases.reverse_point_transaction import (
    ReverseTransactionCommand,
)
from bounded_contexts.reward_points.presentation import family_archive_documents
from bounded_contexts.reward_points.presentation.dependencies import (
    AcceptInvitationDep,
    AddChildDep,
    ApproveIndependenceDep,
    ChangeRewardEventDeadlineDep,
    ConfigureDailyBonusDep,
    CorrectTransactionDep,
    CreateFamilyDep,
    CreateRewardEventDep,
    DeleteRewardEventDep,
    DissolveFamilyDep,
    EditFamilyRulesDep,
    ExportFamilyDep,
    ImportFamilyDep,
    IssueInvitationDep,
    LeaveFamilyDep,
    ListFamiliesDep,
    ListInvitationsDep,
    PeelRewardEventStickerDep,
    ProposeIndependenceDep,
    RecordTransactionDep,
    RedeemInvitationDep,
    RemoveMembershipDep,
    RenameFamilyDep,
    ReorderMembersDep,
    ResetChildPasswordDep,
    ReverseTransactionDep,
    RevokeIndependenceDep,
    RevokeInvitationDep,
    StickRewardEventStickerDep,
    StopDailyBonusDep,
    SuggestReasonsDep,
    ViewFamilyDep,
    ViewLedgerDep,
    ViewRewardEventsDep,
)
from bounded_contexts.reward_points.presentation.schemas import (
    ChildCreateRequest,
    CorrectionCreateRequest,
    CorrectionResponse,
    DailyBonusRequest,
    DailyBonusResponse,
    FamilyArchiveDocument,
    FamilyCreateRequest,
    FamilyDetailResponse,
    FamilyRenameRequest,
    FamilyRulesRequest,
    FamilySummaryResponse,
    ImportedFamilyResponse,
    InvitationAcceptRequest,
    InvitationCreateRequest,
    InvitationRedeemRequest,
    InvitationResponse,
    LedgerResponse,
    MemberOrderRequest,
    MembershipResponse,
    RedeemedInvitationResponse,
    ReversalCreateRequest,
    RewardEventBoardResponse,
    RewardEventCreateRequest,
    RewardEventDeadlineRequest,
    RewardEventResponse,
    StickerResponse,
    TemporaryPasswordResponse,
    TransactionCreateRequest,
    TransactionResponse,
)
from presentation.fastapi.dependencies.auth import require_permission
from shared.application.authenticated_principal import AuthenticatedPrincipal

router = APIRouter(prefix="/api/families", tags=["reward-points"])
logger = logging.getLogger(__name__)

FamilyViewer = Annotated[AuthenticatedPrincipal, Depends(require_permission("family:view"))]
FamilyManager = Annotated[AuthenticatedPrincipal, Depends(require_permission("family:manage"))]
PointViewer = Annotated[AuthenticatedPrincipal, Depends(require_permission("point:view"))]
PointManager = Annotated[AuthenticatedPrincipal, Depends(require_permission("point:manage"))]
# Creating a family makes one a "full-fledged guardian", so the full set of guardian scopes is
# required. This keeps custom roles holding only some of them from producing owners who can
# neither view nor record
FamilyGuardian = Annotated[
    AuthenticatedPrincipal,
    Depends(require_permission("family:view", "family:manage", "point:view", "point:manage")),
]
# An archive holds the whole family (children's ledgers and history), so the caller must be
# able to view both families and ledgers (ADR-0026). Which family can be exported is decided
# further on by the role within the family
ArchiveReader = Annotated[AuthenticatedPrincipal, Depends(require_permission("family:view", "point:view"))]


def _to_membership(dto: MembershipDTO) -> MembershipResponse:
    return MembershipResponse(
        id=dto.id,
        display_name=dto.display_name,
        role=dto.role,
        is_linked=dto.is_linked,
        is_me=dto.is_me,
        username=dto.username,
        ledger_id=dto.ledger_id,
        balance=dto.balance,
        daily_bonus=_to_daily_bonus(dto.daily_bonus) if dto.daily_bonus else None,
        independence_proposed=dto.independence_proposed,
        can_reset_password=dto.can_reset_password,
        can_propose_independence=dto.can_propose_independence,
        can_remove=dto.can_remove,
    )


def _to_family(dto: FamilyDetailDTO) -> FamilyDetailResponse:
    return FamilyDetailResponse(
        id=dto.id,
        name=dto.name,
        rules=dto.rules,
        my_membership_id=dto.my_membership_id,
        my_role=dto.my_role,
        memberships=[_to_membership(member) for member in dto.memberships],
    )


def _to_invitation(dto: InvitationDTO) -> InvitationResponse:
    return InvitationResponse(
        id=dto.id,
        role=dto.role,
        target_membership_id=dto.target_membership_id,
        target_display_name=dto.target_display_name,
        expires_at=dto.expires_at,
        code=dto.code,
    )


def _to_redeemed(dto: RedeemedInvitationDTO) -> RedeemedInvitationResponse:
    return RedeemedInvitationResponse(
        family_id=dto.family_id,
        family_name=dto.family_name,
        membership_id=dto.membership_id,
        role=dto.role,
        username=dto.username,
    )


def _to_transaction(dto: TransactionDTO) -> TransactionResponse:
    return TransactionResponse(
        id=dto.id,
        amount=dto.amount,
        reason=dto.reason,
        occurred_at=dto.occurred_at,
        created_at=dto.created_at,
        reversal_of_id=dto.reversal_of_id,
        corrects_id=dto.corrects_id,
        is_reversed=dto.is_reversed,
        granted_by=dto.granted_by,
    )


def _to_daily_bonus(dto: DailyBonusDTO) -> DailyBonusResponse:
    return DailyBonusResponse(
        ledger_id=dto.ledger_id,
        amount=dto.amount,
        reason=dto.reason,
        starts_on=dto.starts_on,
        granted_through=dto.granted_through,
    )


def _to_reward_event(dto: RewardEventDTO) -> RewardEventResponse:
    return RewardEventResponse(
        id=dto.id,
        ledger_id=dto.ledger_id,
        title=dto.title,
        reward_points=dto.reward_points,
        goal_count=dto.goal_count,
        stickers=[StickerResponse(number=s.number, stuck_at=s.stuck_at) for s in dto.stickers],
        completed_at=dto.completed_at,
        created_at=dto.created_at,
        deadline=dto.deadline,
        is_expired=dto.is_expired,
    )


def _to_correction(dto: CorrectionDTO) -> CorrectionResponse:
    return CorrectionResponse(
        reversal=_to_transaction(dto.reversal),
        correction=_to_transaction(dto.correction),
    )


# --- Accepting invitations (unauthenticated) ---------------------------------


@router.post(
    "/invitations/redeem",
    status_code=status.HTTP_201_CREATED,
    response_model=RedeemedInvitationResponse,
)
def redeem_invitation(body: InvitationRedeemRequest, use_case: RedeemInvitationDep) -> RedeemedInvitationResponse:
    """Create an account with an invitation code and join the family.

    The caller is not logged in after creation. Log in as usual with the chosen
    ``username`` and password.
    """
    dto = use_case.execute(
        RedeemInvitationCommand(
            code=body.code,
            username=body.username,
            password=body.password,
            display_name=body.display_name,
        )
    )
    logger.info("invitation_redeemed", extra={"family_id": dto.family_id})
    return _to_redeemed(dto)


@router.post("/invitations/accept", response_model=RedeemedInvitationResponse)
def accept_invitation(
    body: InvitationAcceptRequest,
    use_case: AcceptInvitationDep,
    principal: FamilyViewer,
) -> RedeemedInvitationResponse:
    """Someone who already has an account joins a family with an invitation code.

    Only accounts that can be guardians may use a parent invitation (ADR-0018).
    """
    dto = use_case.execute(
        AcceptInvitationCommand(
            code=body.code,
            account_id=principal.user_id,
            username=principal.username,
            display_name=body.display_name or principal.display_name,
            can_guard=principal.can("family:manage", "point:manage"),
        )
    )
    logger.info("invitation_accepted", extra={"family_id": dto.family_id})
    return _to_redeemed(dto)


# --- Family ------------------------------------------------------------------


@router.get("", response_model=list[FamilySummaryResponse])
def list_families(use_case: ListFamiliesDep, principal: FamilyViewer) -> list[FamilySummaryResponse]:
    """Return the families the caller belongs to (multiple memberships allowed)."""
    return [
        FamilySummaryResponse(
            id=dto.id,
            name=dto.name,
            my_membership_id=dto.my_membership_id,
            my_role=dto.my_role,
            member_count=dto.member_count,
        )
        for dto in use_case.execute(principal.user_id)
    ]


@router.post("", status_code=status.HTTP_201_CREATED, response_model=FamilyDetailResponse)
def create_family(
    body: FamilyCreateRequest, use_case: CreateFamilyDep, principal: FamilyGuardian
) -> FamilyDetailResponse:
    """Create a family. The creator becomes the owner.

    Parents (member role) hold the full set of guardian scopes and can create one. Children
    (guest) and system administrators (admin) are stopped by scope (ADR-0018).
    """
    dto = use_case.execute(
        CreateFamilyCommand(
            name=body.name,
            account_id=principal.user_id,
            display_name=body.display_name or principal.display_name,
        )
    )
    logger.info("family_created", extra={"family_id": dto.id})
    return _to_family(dto)


# --- Archives (backup; ADR-0026) ---------------------------------------------


@router.post("/import", status_code=status.HTTP_201_CREATED, response_model=ImportedFamilyResponse)
def import_family(
    body: FamilyArchiveDocument, use_case: ImportFamilyDep, principal: FamilyGuardian
) -> ImportedFamilyResponse:
    """Rebuild a family from an archive (restore).

    A **new family** is created and the caller becomes its owner. It cannot be merged into
    an existing family, so it cannot be called while belonging to one
    (``already_belongs_to_family``).

    Members other than the owner come back without linked accounts; people re-join via
    invitation codes. Children's ledgers come back with their records, so an invited child
    finds their history intact.
    """
    dto = use_case.execute(
        ImportFamilyCommand(
            account_id=principal.user_id,
            archive=family_archive_documents.to_dto(body),
        )
    )
    logger.info(
        "family_imported",
        extra={
            "family_id": dto.family_id,
            "member_count": dto.member_count,
            "transaction_count": dto.transaction_count,
        },
    )
    return ImportedFamilyResponse(
        family_id=dto.family_id,
        name=dto.name,
        member_count=dto.member_count,
        transaction_count=dto.transaction_count,
    )


@router.get("/{family_id}/export", response_model=FamilyArchiveDocument)
def export_family(family_id: int, use_case: ExportFamilyDep, principal: ArchiveReader) -> FamilyArchiveDocument:
    """Export the whole family as an archive (parents only).

    Members, children's ledgers, records and daily bonuses go into one JSON. **Accounts are
    not included** — no login IDs, passwords or invitation codes, so nobody's account can be
    taken over from this archive.

    Sending it as-is to ``POST /api/families/import`` restores it.
    """
    archive = use_case.execute(family_id=family_id, account_id=principal.user_id)
    logger.info("family_exported", extra={"family_id": family_id, "member_count": len(archive.members)})
    return family_archive_documents.to_document(archive)


# --- Family (continued) ------------------------------------------------------


@router.get("/{family_id}", response_model=FamilyDetailResponse)
def view_family(family_id: int, use_case: ViewFamilyDep, principal: FamilyViewer) -> FamilyDetailResponse:
    """Members, plus the ledgers and balances within the visible range.

    Whether each per-member operation is allowed (``can_*``) depends on both the role
    within the family and ``family:manage`` (ADR-0019). The entry points for removal,
    requesting independence and temporary passwords all require ``family:manage``, so they
    are not offered to callers lacking it.
    """
    dto = use_case.execute(
        family_id=family_id,
        account_id=principal.user_id,
        can_manage=principal.can("family:manage"),
    )
    return _to_family(dto)


@router.patch("/{family_id}", response_model=FamilyDetailResponse)
def rename_family(
    *,
    family_id: int,
    body: FamilyRenameRequest,
    use_case: RenameFamilyDep,
    principal: FamilyManager,
) -> FamilyDetailResponse:
    """Rename the family (owner only)."""
    dto = use_case.execute(family_id=family_id, account_id=principal.user_id, name=body.name)
    logger.info("family_renamed", extra={"family_id": family_id})
    return _to_family(dto)


@router.put("/{family_id}/rules", response_model=FamilyDetailResponse)
def edit_family_rules(
    *,
    family_id: int,
    body: FamilyRulesRequest,
    use_case: EditFamilyRulesDep,
    principal: FamilyManager,
) -> FamilyDetailResponse:
    """Rewrite the family's agreed rules (parent members; ADR-0027).

    One per family; every member reads the same text. Point grants are unaffected — it only
    records what was agreed; amounts are decided by parents' records and the daily bonus.

    Omitting ``rules`` (``null``) or sending it empty clears the existing rules.
    """
    dto = use_case.execute(family_id=family_id, account_id=principal.user_id, rules=body.rules)
    logger.info("family_rules_edited", extra={"family_id": family_id})
    return _to_family(dto)


@router.delete("/{family_id}", status_code=status.HTTP_204_NO_CONTENT)
def dissolve_family(family_id: int, use_case: DissolveFamilyDep, principal: FamilyManager) -> None:
    """Dissolve the family (owner only; no other members may remain)."""
    use_case.execute(family_id=family_id, account_id=principal.user_id)
    logger.info("family_dissolved", extra={"family_id": family_id})


@router.post("/{family_id}/leave", status_code=status.HTTP_204_NO_CONTENT)
def leave_family(family_id: int, use_case: LeaveFamilyDep, principal: FamilyViewer) -> None:
    """Leave the family (parents only, and only if another parent remains).

    Afterwards the caller is in the initial state and may create a family or accept an
    invitation again.
    """
    use_case.execute(family_id=family_id, account_id=principal.user_id)
    logger.info("family_left", extra={"family_id": family_id})


@router.post(
    "/{family_id}/memberships",
    status_code=status.HTTP_201_CREATED,
    response_model=MembershipResponse,
)
def add_child(
    *,
    family_id: int,
    body: ChildCreateRequest,
    use_case: AddChildDep,
    principal: FamilyManager,
) -> MembershipResponse:
    """Create a child's membership and ledger. The account is linked later via invitation code."""
    dto = use_case.execute(
        AddChildMembershipCommand(
            family_id=family_id,
            account_id=principal.user_id,
            display_name=body.display_name,
        )
    )
    logger.info("child_membership_added", extra={"family_id": family_id, "membership_id": dto.id})
    return _to_membership(dto)


@router.delete("/{family_id}/memberships/{membership_id}", status_code=status.HTTP_204_NO_CONTENT)
def remove_membership(
    *,
    family_id: int,
    membership_id: int,
    use_case: RemoveMembershipDep,
    principal: FamilyManager,
) -> None:
    display_account_id = use_case.execute(
        family_id=family_id, membership_id=membership_id, account_id=principal.user_id
    )
    if display_account_id is not None:
        # Log with the same text as when an operator detaches it (who, which family, which device; ADR-0047)
        logger.info(
            "display_removed: family_id=%s account_id=%s remover_id=%s",
            family_id,
            display_account_id,
            principal.user_id,
        )
        return
    logger.info("membership_removed", extra={"family_id": family_id, "membership_id": membership_id})


@router.put("/{family_id}/member-order", response_model=FamilyDetailResponse)
def reorder_members(
    *,
    family_id: int,
    body: MemberOrderRequest,
    use_case: ReorderMembersDep,
    principal: FamilyManager,
) -> FamilyDetailResponse:
    """Set the order in which children are listed (parent members).

    Both navigation and the dashboard follow this order. There is one order per family, the
    same for every viewer.
    """
    dto = use_case.execute(
        family_id=family_id,
        account_id=principal.user_id,
        membership_ids=body.membership_ids,
    )
    logger.info("family_members_reordered", extra={"family_id": family_id})
    return _to_family(dto)


@router.post(
    "/{family_id}/memberships/{membership_id}/password-reset",
    response_model=TemporaryPasswordResponse,
)
def reset_child_password(
    *,
    family_id: int,
    membership_id: int,
    use_case: ResetChildPasswordDep,
    principal: FamilyManager,
) -> TemporaryPasswordResponse:
    """Issue a temporary password for a child (ADR-0011).

    The issuance is recorded in the structured log and the ``log`` table. The plaintext is
    returned only in this response.
    """
    dto = use_case.execute(family_id=family_id, membership_id=membership_id, account_id=principal.user_id)
    # Record the issuance (issuer, target, time). The plaintext password is never logged (ADR-0011).
    # The issuer is also attached to the request log as user.id_hash (an identifier free of PII).
    logger.info(
        "temporary_password_issued",
        extra={
            "family_id": family_id,
            "membership_id": membership_id,
            "issued_by_membership_id": dto.issued_by_membership_id,
        },
    )
    return TemporaryPasswordResponse(
        membership_id=dto.membership_id,
        username=dto.username,
        password=dto.password,
        expires_at=dto.expires_at,
    )


# --- Independence (ADR-0014) -------------------------------------------------


@router.post(
    "/{family_id}/memberships/{membership_id}/independence-proposal",
    response_model=MembershipResponse,
)
def propose_independence(
    *,
    family_id: int,
    membership_id: int,
    use_case: ProposeIndependenceDep,
    principal: FamilyManager,
) -> MembershipResponse:
    """Request a child's independence (parent members). Established once the child approves."""
    membership = use_case.execute(family_id=family_id, membership_id=membership_id, account_id=principal.user_id)
    logger.info("independence_proposed", extra={"family_id": family_id, "membership_id": membership_id})
    return _to_membership(
        MembershipDTO(
            id=membership.id,
            display_name=membership.display_name_value,
            role=membership.role,
            is_linked=membership.is_linked,
            is_me=False,
            username=None,
            ledger_id=None,
            balance=None,
            independence_proposed=membership.independence_proposed,
        )
    )


@router.delete(
    "/{family_id}/memberships/{membership_id}/independence-proposal",
    status_code=status.HTTP_204_NO_CONTENT,
)
def revoke_independence_proposal(
    *,
    family_id: int,
    membership_id: int,
    use_case: RevokeIndependenceDep,
    principal: FamilyManager,
) -> None:
    """Withdraw an independence request (any time before approval)."""
    use_case.execute(family_id=family_id, membership_id=membership_id, account_id=principal.user_id)
    logger.info("independence_proposal_revoked", extra={"family_id": family_id, "membership_id": membership_id})


@router.post("/{family_id}/independence", status_code=status.HTTP_204_NO_CONTENT)
def approve_independence(
    family_id: int,
    use_case: ApproveIndependenceDep,
    principal: FamilyViewer,
) -> None:
    """Approve independence (by the child who received the request).

    Once established, the membership, ledger and records are removed from the family and
    the child becomes a member with no family (able to create a family or accept an
    invitation again).
    """
    use_case.execute(family_id=family_id, account_id=principal.user_id)
    logger.info("independence_approved", extra={"family_id": family_id})


# --- Issuing invitations -----------------------------------------------------


@router.get("/{family_id}/invitations", response_model=list[InvitationResponse])
def list_invitations(
    family_id: int, use_case: ListInvitationsDep, principal: FamilyManager
) -> list[InvitationResponse]:
    return [_to_invitation(dto) for dto in use_case.execute(family_id=family_id, account_id=principal.user_id)]


@router.post(
    "/{family_id}/invitations",
    status_code=status.HTTP_201_CREATED,
    response_model=InvitationResponse,
)
def issue_invitation(
    *,
    family_id: int,
    body: InvitationCreateRequest,
    use_case: IssueInvitationDep,
    principal: FamilyManager,
) -> InvitationResponse:
    dto = use_case.execute(
        IssueInvitationCommand(
            family_id=family_id,
            account_id=principal.user_id,
            role=body.role,
            target_membership_id=body.target_membership_id,
        )
    )
    logger.info("invitation_issued", extra={"family_id": family_id, "role": dto.role.value})
    return _to_invitation(dto)


@router.delete("/{family_id}/invitations/{invitation_id}", status_code=status.HTTP_204_NO_CONTENT)
def revoke_invitation(
    *,
    family_id: int,
    invitation_id: int,
    use_case: RevokeInvitationDep,
    principal: FamilyManager,
) -> None:
    use_case.execute(family_id=family_id, invitation_id=invitation_id, account_id=principal.user_id)
    logger.info("invitation_revoked", extra={"family_id": family_id})


# --- Ledger ------------------------------------------------------------------


@router.get("/{family_id}/reason-suggestions", response_model=list[str])
def suggest_reasons(family_id: int, use_case: SuggestReasonsDep, principal: PointManager) -> list[str]:
    """Reasons often used in the family (input suggestions). Most frequent first."""
    return use_case.execute(family_id=family_id, account_id=principal.user_id)


@router.get("/{family_id}/ledgers/{ledger_id}", response_model=LedgerResponse)
def view_ledger(ledger_id: int, use_case: ViewLedgerDep, principal: PointViewer) -> LedgerResponse:
    """Balance and history. The UI uses ``can_modify`` to decide whether to show editing UI."""
    dto = use_case.execute(ledger_id=ledger_id, account_id=principal.user_id)
    return LedgerResponse(
        ledger_id=dto.ledger_id,
        family_id=dto.family_id,
        membership_id=dto.membership_id,
        display_name=dto.display_name,
        balance=dto.balance,
        can_modify=dto.can_modify,
        transactions=[_to_transaction(transaction) for transaction in dto.transactions],
        daily_bonus=_to_daily_bonus(dto.daily_bonus) if dto.daily_bonus else None,
    )


@router.post(
    "/{family_id}/ledgers/{ledger_id}/transactions",
    status_code=status.HTTP_201_CREATED,
    response_model=TransactionResponse,
)
def record_transaction(
    *,
    ledger_id: int,
    body: TransactionCreateRequest,
    use_case: RecordTransactionDep,
    principal: PointManager,
) -> TransactionResponse:
    """Append one addition/spending row (distinguished by sign).

    If the same ``idempotency_key`` arrives twice, the first record is returned.
    """
    dto = use_case.execute(
        RecordTransactionCommand(
            ledger_id=ledger_id,
            account_id=principal.user_id,
            amount=body.amount,
            reason=body.reason,
            idempotency_key=body.idempotency_key,
            occurred_at=body.occurred_at,
        )
    )
    logger.info("point_transaction_recorded", extra={"ledger_id": ledger_id, "amount": dto.amount})
    return _to_transaction(dto)


@router.post(
    "/{family_id}/ledgers/{ledger_id}/transactions/{transaction_id}/reversals",
    status_code=status.HTTP_201_CREATED,
    response_model=TransactionResponse,
)
def reverse_transaction(
    *,
    ledger_id: int,
    transaction_id: int,
    body: ReversalCreateRequest,
    use_case: ReverseTransactionDep,
    principal: PointManager,
) -> TransactionResponse:
    """Reverse a record. The original stays; a row with the opposite sign is added (ADR-0010)."""
    dto = use_case.execute(
        ReverseTransactionCommand(
            ledger_id=ledger_id,
            transaction_id=transaction_id,
            account_id=principal.user_id,
            idempotency_key=body.idempotency_key,
        )
    )
    logger.info(
        "point_transaction_reversed",
        extra={"ledger_id": ledger_id, "transaction_id": transaction_id},
    )
    return _to_transaction(dto)


@router.post(
    "/{family_id}/ledgers/{ledger_id}/transactions/{transaction_id}/corrections",
    status_code=status.HTTP_201_CREATED,
    response_model=CorrectionResponse,
)
def correct_transaction(
    *,
    ledger_id: int,
    transaction_id: int,
    body: CorrectionCreateRequest,
    use_case: CorrectTransactionDep,
    principal: PointManager,
) -> CorrectionResponse:
    """Fix an input mistake. The original record is not rewritten; two rows are added: a
    reversal and the correct content (ADR-0022).

    Omitting ``occurred_at`` inherits the original record's occurrence time. An already
    reversed record cannot be corrected (409).
    """
    dto = use_case.execute(
        CorrectTransactionCommand(
            ledger_id=ledger_id,
            transaction_id=transaction_id,
            account_id=principal.user_id,
            amount=body.amount,
            reason=body.reason,
            occurred_at=body.occurred_at,
            idempotency_key=body.idempotency_key,
        )
    )
    logger.info(
        "point_transaction_corrected",
        extra={
            "ledger_id": ledger_id,
            "transaction_id": transaction_id,
            "amount": dto.correction.amount,
        },
    )
    return _to_correction(dto)


# --- Daily bonus (ADR-0024) --------------------------------------------------


@router.put("/{family_id}/ledgers/{ledger_id}/daily-bonus", response_model=DailyBonusResponse)
def configure_daily_bonus(
    *,
    ledger_id: int,
    body: DailyBonusRequest,
    use_case: ConfigureDailyBonusDep,
    principal: PointManager,
) -> DailyBonusResponse:
    """Set how much to add each day (overwrites any existing setting).

    Granting starts from **the next date change**. This call adds no rows to the ledger, so
    the time of day it is set does not affect what is received. The current setting appears
    in the ledger's (``GET .../ledgers/{id}``) ``daily_bonus``.
    """
    dto = use_case.execute(
        ConfigureDailyBonusCommand(
            ledger_id=ledger_id,
            account_id=principal.user_id,
            amount=body.amount,
            reason=body.reason,
        )
    )
    logger.info("daily_bonus_configured", extra={"ledger_id": ledger_id, "amount": dto.amount})
    return _to_daily_bonus(dto)


@router.delete("/{family_id}/ledgers/{ledger_id}/daily-bonus", status_code=status.HTTP_204_NO_CONTENT)
def stop_daily_bonus(
    *,
    ledger_id: int,
    use_case: StopDailyBonusDep,
    principal: PointManager,
) -> None:
    """Stop the daily bonus. Points already granted remain.

    Succeeds even with no setting (the request to stop is already satisfied).
    """
    use_case.execute(ledger_id=ledger_id, account_id=principal.user_id)
    logger.info("daily_bonus_stopped", extra={"ledger_id": ledger_id})


# --- Reward events (ADR-0042) ------------------------------------------------


def _event_path(suffix: str = "") -> str:
    return "/{family_id}/ledgers/{ledger_id}/events" + suffix


@router.get(_event_path(), response_model=RewardEventBoardResponse)
def view_reward_events(
    ledger_id: int, use_case: ViewRewardEventsDep, principal: PointViewer
) -> RewardEventBoardResponse:
    """Return the child's events (effort cards) in creation order.

    The child can also see their own cards. If ``can_modify`` is false, the UI offers no way
    to stick or create.
    """
    dto = use_case.execute(ledger_id=ledger_id, account_id=principal.user_id)
    return RewardEventBoardResponse(
        ledger_id=dto.ledger_id,
        display_name=dto.display_name,
        can_modify=dto.can_modify,
        events=[_to_reward_event(event) for event in dto.events],
    )


@router.post(_event_path(), status_code=status.HTTP_201_CREATED, response_model=RewardEventResponse)
def create_reward_event(
    *,
    ledger_id: int,
    body: RewardEventCreateRequest,
    use_case: CreateRewardEventDep,
    principal: PointManager,
) -> RewardEventResponse:
    """Create an event. ``goal_count`` slots are laid out; filling all adds ``reward_points`` to the ledger.

    With ``deadline`` set, the event expires if not filled by the end of that day (a past date is 400).
    """
    dto = use_case.execute(
        CreateRewardEventCommand(
            ledger_id=ledger_id,
            account_id=principal.user_id,
            title=body.title,
            reward_points=body.reward_points,
            goal_count=body.goal_count,
            deadline=body.deadline,
        )
    )
    logger.info("reward_event_created", extra={"ledger_id": ledger_id, "event_id": dto.id})
    return _to_reward_event(dto)


@router.put(_event_path("/{event_id}/deadline"), response_model=RewardEventResponse)
def change_reward_event_deadline(
    *,
    ledger_id: int,
    event_id: int,
    body: RewardEventDeadlineRequest,
    use_case: ChangeRewardEventDeadlineDep,
    principal: PointManager,
) -> RewardEventResponse:
    """Reset the deadline (null for none). An expired card can be stuck again once extended."""
    dto = use_case.execute(
        ChangeDeadlineCommand(
            ledger_id=ledger_id, event_id=event_id, account_id=principal.user_id, deadline=body.deadline
        )
    )
    logger.info("reward_event_deadline_changed", extra={"ledger_id": ledger_id, "event_id": event_id})
    return _to_reward_event(dto)


@router.put(_event_path("/{event_id}/stickers/{number}"), response_model=RewardEventResponse)
def stick_reward_event_sticker(
    *,
    ledger_id: int,
    event_id: int,
    number: int,
    use_case: StickRewardEventStickerDep,
    principal: PointManager,
) -> RewardEventResponse:
    """Stick sticker *number* (one achievement done).

    ``number`` is the next number to stick (current count + 1). For a number already stuck,
    nothing happens and the current state is returned, so resending the same tap never yields
    two stickers. When the last slot fills, ``reward_points`` is added to the ledger and
    ``completed_at`` is set.
    """
    dto = use_case.execute(
        StickerCommand(ledger_id=ledger_id, event_id=event_id, account_id=principal.user_id, number=number)
    )
    logger.info(
        "reward_event_sticker_stuck",
        extra={
            "ledger_id": ledger_id,
            "event_id": event_id,
            "number": number,
            "completed": dto.completed_at is not None,
        },
    )
    return _to_reward_event(dto)


@router.delete(_event_path("/{event_id}/stickers/{number}"), response_model=RewardEventResponse)
def peel_reward_event_sticker(
    *,
    ledger_id: int,
    event_id: int,
    number: int,
    use_case: PeelRewardEventStickerDep,
    principal: PointManager,
) -> RewardEventResponse:
    """Peel the last stuck sticker (undo a mis-tap). Not possible after completion."""
    dto = use_case.execute(
        StickerCommand(ledger_id=ledger_id, event_id=event_id, account_id=principal.user_id, number=number)
    )
    logger.info("reward_event_sticker_peeled", extra={"ledger_id": ledger_id, "event_id": event_id, "number": number})
    return _to_reward_event(dto)


@router.delete(_event_path("/{event_id}"), status_code=status.HTTP_204_NO_CONTENT)
def delete_reward_event(
    *,
    ledger_id: int,
    event_id: int,
    use_case: DeleteRewardEventDep,
    principal: PointManager,
) -> None:
    """Delete an event. Points added on completion remain in the ledger."""
    use_case.execute(ledger_id=ledger_id, event_id=event_id, account_id=principal.user_id)
    logger.info("reward_event_deleted", extra={"ledger_id": ledger_id, "event_id": event_id})
