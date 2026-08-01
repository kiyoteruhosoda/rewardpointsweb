"""reward_points コンテキストの API。

認可は 2 段構えになっている。

1. **scope**（``family:view`` / ``point:manage`` 等）— その操作を行える立場か
2. **家族の中での立場**（owner / parent / child）— *その* 家族・台帳を触れるか

1 はここで宣言し、2 は Application 層の
:class:`~bounded_contexts.reward_points.application.family_access_resolver.FamilyAccessResolver`
が判定する。``point:manage`` を持つ利用者でも、所属していない家族は触れない。

招待の受諾（``/invitations/redeem``）だけは **未認証** で呼べる。子はまだ
アカウントを持たないため（ADR-0011）。
"""

from __future__ import annotations

import logging
from typing import Annotated

from fastapi import APIRouter, Depends, status

from bounded_contexts.reward_points.application.dto.family_dto import (
    FamilyDetailDTO,
    InvitationDTO,
    MembershipDTO,
    RedeemedInvitationDTO,
)
from bounded_contexts.reward_points.application.dto.ledger_dto import TransactionDTO
from bounded_contexts.reward_points.application.use_cases.accept_invitation import AcceptInvitationCommand
from bounded_contexts.reward_points.application.use_cases.add_child_membership import (
    AddChildMembershipCommand,
)
from bounded_contexts.reward_points.application.use_cases.create_family import CreateFamilyCommand
from bounded_contexts.reward_points.application.use_cases.issue_invitation import IssueInvitationCommand
from bounded_contexts.reward_points.application.use_cases.record_point_transaction import (
    RecordTransactionCommand,
)
from bounded_contexts.reward_points.application.use_cases.redeem_invitation import RedeemInvitationCommand
from bounded_contexts.reward_points.application.use_cases.reverse_point_transaction import (
    ReverseTransactionCommand,
)
from bounded_contexts.reward_points.presentation.dependencies import (
    AcceptInvitationDep,
    AddChildDep,
    CreateFamilyDep,
    IssueInvitationDep,
    ListFamiliesDep,
    ListInvitationsDep,
    RecordTransactionDep,
    RedeemInvitationDep,
    RemoveMembershipDep,
    ResetChildPasswordDep,
    ReverseTransactionDep,
    RevokeInvitationDep,
    ViewFamilyDep,
    ViewLedgerDep,
)
from bounded_contexts.reward_points.presentation.schemas import (
    ChildCreateRequest,
    FamilyCreateRequest,
    FamilyDetailResponse,
    FamilySummaryResponse,
    InvitationAcceptRequest,
    InvitationCreateRequest,
    InvitationRedeemRequest,
    InvitationResponse,
    LedgerResponse,
    MembershipResponse,
    RedeemedInvitationResponse,
    ReversalCreateRequest,
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
    )


def _to_family(dto: FamilyDetailDTO) -> FamilyDetailResponse:
    return FamilyDetailResponse(
        id=dto.id,
        name=dto.name,
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
        is_reversed=dto.is_reversed,
        granted_by=dto.granted_by,
    )


# --- 招待の受諾（未認証） ----------------------------------------------------


@router.post(
    "/invitations/redeem",
    status_code=status.HTTP_201_CREATED,
    response_model=RedeemedInvitationResponse,
)
async def redeem_invitation(body: InvitationRedeemRequest, use_case: RedeemInvitationDep) -> RedeemedInvitationResponse:
    """招待コードでアカウントを作り、家族へ加わる。

    作成後はまだログインしていない。設定した ``username`` とパスワードで
    通常どおりログインする。
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
async def accept_invitation(
    body: InvitationAcceptRequest,
    use_case: AcceptInvitationDep,
    principal: FamilyViewer,
) -> RedeemedInvitationResponse:
    """すでにアカウントを持つ人が、招待コードで家族へ加わる。"""
    dto = use_case.execute(
        AcceptInvitationCommand(
            code=body.code,
            account_id=principal.user_id,
            username=principal.username,
            display_name=body.display_name or principal.display_name,
        )
    )
    logger.info("invitation_accepted", extra={"family_id": dto.family_id})
    return _to_redeemed(dto)


# --- 家族 --------------------------------------------------------------------


@router.get("", response_model=list[FamilySummaryResponse])
async def list_families(use_case: ListFamiliesDep, principal: FamilyViewer) -> list[FamilySummaryResponse]:
    """自分が所属する家族を返す（複数所属を許す）。"""
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
async def create_family(
    body: FamilyCreateRequest, use_case: CreateFamilyDep, principal: FamilyManager
) -> FamilyDetailResponse:
    dto = use_case.execute(
        CreateFamilyCommand(
            name=body.name,
            account_id=principal.user_id,
            display_name=body.display_name or principal.display_name,
        )
    )
    logger.info("family_created", extra={"family_id": dto.id})
    return _to_family(dto)


@router.get("/{family_id}", response_model=FamilyDetailResponse)
async def view_family(family_id: int, use_case: ViewFamilyDep, principal: FamilyViewer) -> FamilyDetailResponse:
    return _to_family(use_case.execute(family_id=family_id, account_id=principal.user_id))


@router.post(
    "/{family_id}/memberships",
    status_code=status.HTTP_201_CREATED,
    response_model=MembershipResponse,
)
async def add_child(
    family_id: int,
    body: ChildCreateRequest,
    use_case: AddChildDep,
    principal: FamilyManager,
) -> MembershipResponse:
    """子の参加と台帳を作る。アカウントは招待コードで後から結び付ける。"""
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
async def remove_membership(
    family_id: int,
    membership_id: int,
    use_case: RemoveMembershipDep,
    principal: FamilyManager,
) -> None:
    use_case.execute(family_id=family_id, membership_id=membership_id, account_id=principal.user_id)
    logger.info("membership_removed", extra={"family_id": family_id, "membership_id": membership_id})


@router.post(
    "/{family_id}/memberships/{membership_id}/password-reset",
    response_model=TemporaryPasswordResponse,
)
async def reset_child_password(
    family_id: int,
    membership_id: int,
    use_case: ResetChildPasswordDep,
    principal: FamilyManager,
) -> TemporaryPasswordResponse:
    """子の一時パスワードを発行する（ADR-0011）。

    発行の事実は構造化ログと ``log`` テーブルに残る。平文はこの応答でだけ返す。
    """
    dto = use_case.execute(family_id=family_id, membership_id=membership_id, account_id=principal.user_id)
    logger.info(
        "temporary_password_issued",
        extra={"family_id": family_id, "membership_id": membership_id},
    )
    return TemporaryPasswordResponse(
        membership_id=dto.membership_id,
        username=dto.username,
        password=dto.password,
        expires_at=dto.expires_at,
    )


# --- 招待の発行 --------------------------------------------------------------


@router.get("/{family_id}/invitations", response_model=list[InvitationResponse])
async def list_invitations(
    family_id: int, use_case: ListInvitationsDep, principal: FamilyManager
) -> list[InvitationResponse]:
    return [_to_invitation(dto) for dto in use_case.execute(family_id=family_id, account_id=principal.user_id)]


@router.post(
    "/{family_id}/invitations",
    status_code=status.HTTP_201_CREATED,
    response_model=InvitationResponse,
)
async def issue_invitation(
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
async def revoke_invitation(
    family_id: int,
    invitation_id: int,
    use_case: RevokeInvitationDep,
    principal: FamilyManager,
) -> None:
    use_case.execute(family_id=family_id, invitation_id=invitation_id, account_id=principal.user_id)
    logger.info("invitation_revoked", extra={"family_id": family_id})


# --- 台帳 --------------------------------------------------------------------


@router.get("/{family_id}/ledgers/{ledger_id}", response_model=LedgerResponse)
async def view_ledger(ledger_id: int, use_case: ViewLedgerDep, principal: PointViewer) -> LedgerResponse:
    """残高と履歴。``can_modify`` で画面側が変更 UI の出し分けを決める。"""
    dto = use_case.execute(ledger_id=ledger_id, account_id=principal.user_id)
    return LedgerResponse(
        ledger_id=dto.ledger_id,
        family_id=dto.family_id,
        membership_id=dto.membership_id,
        display_name=dto.display_name,
        balance=dto.balance,
        can_modify=dto.can_modify,
        transactions=[_to_transaction(transaction) for transaction in dto.transactions],
    )


@router.post(
    "/{family_id}/ledgers/{ledger_id}/transactions",
    status_code=status.HTTP_201_CREATED,
    response_model=TransactionResponse,
)
async def record_transaction(
    ledger_id: int,
    body: TransactionCreateRequest,
    use_case: RecordTransactionDep,
    principal: PointManager,
) -> TransactionResponse:
    """加算・消費を 1 行追記する（符号で区別する）。

    同じ ``idempotency_key`` で 2 度届いた場合は、1 度目のレコードを返す。
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
async def reverse_transaction(
    ledger_id: int,
    transaction_id: int,
    body: ReversalCreateRequest,
    use_case: ReverseTransactionDep,
    principal: PointManager,
) -> TransactionResponse:
    """記録を打ち消す。元のレコードは残したまま、逆符号の行を足す（ADR-0010）。"""
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
