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
from bounded_contexts.reward_points.application.dto.ledger_dto import CorrectionDTO, TransactionDTO
from bounded_contexts.reward_points.application.use_cases.accept_invitation import AcceptInvitationCommand
from bounded_contexts.reward_points.application.use_cases.add_child_membership import (
    AddChildMembershipCommand,
)
from bounded_contexts.reward_points.application.use_cases.correct_point_transaction import (
    CorrectTransactionCommand,
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
    ApproveIndependenceDep,
    CorrectTransactionDep,
    CreateFamilyDep,
    DissolveFamilyDep,
    IssueInvitationDep,
    LeaveFamilyDep,
    ListFamiliesDep,
    ListInvitationsDep,
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
    SuggestReasonsDep,
    ViewFamilyDep,
    ViewLedgerDep,
)
from bounded_contexts.reward_points.presentation.schemas import (
    ChildCreateRequest,
    CorrectionCreateRequest,
    CorrectionResponse,
    FamilyCreateRequest,
    FamilyDetailResponse,
    FamilyRenameRequest,
    FamilySummaryResponse,
    InvitationAcceptRequest,
    InvitationCreateRequest,
    InvitationRedeemRequest,
    InvitationResponse,
    LedgerResponse,
    MemberOrderRequest,
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
# 家族の作成は「一人前の保護者」になる操作なので、保護者の scope 一式を要求する。
# 一部しか持たないカスタムロールが、閲覧も記録もできない owner を生まないため
FamilyGuardian = Annotated[
    AuthenticatedPrincipal,
    Depends(require_permission("family:view", "family:manage", "point:view", "point:manage")),
]


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
        independence_proposed=dto.independence_proposed,
        can_reset_password=dto.can_reset_password,
        can_propose_independence=dto.can_propose_independence,
        can_remove=dto.can_remove,
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
        corrects_id=dto.corrects_id,
        is_reversed=dto.is_reversed,
        granted_by=dto.granted_by,
    )


def _to_correction(dto: CorrectionDTO) -> CorrectionResponse:
    return CorrectionResponse(
        reversal=_to_transaction(dto.reversal),
        correction=_to_transaction(dto.correction),
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
    """すでにアカウントを持つ人が、招待コードで家族へ加わる。

    親（parent）の招待を使えるのは保護者になれるアカウントだけ（ADR-0018）。
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
    body: FamilyCreateRequest, use_case: CreateFamilyDep, principal: FamilyGuardian
) -> FamilyDetailResponse:
    """家族を作る。作った人が owner になる。

    親（member ロール）は保護者の scope 一式を持つので作れる。子（guest）と
    システム管理者（admin）は scope で止まる（ADR-0018）。
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


@router.get("/{family_id}", response_model=FamilyDetailResponse)
async def view_family(family_id: int, use_case: ViewFamilyDep, principal: FamilyViewer) -> FamilyDetailResponse:
    """参加者と、見える範囲の台帳・残高。

    参加者ごとの操作の可否（``can_*``）は、家族の中での立場と ``family:manage``
    の両方から決まる（ADR-0019）。除名・独立の指示・一時パスワードの入口は
    どれも ``family:manage`` を要求するため、持っていない呼び出し元には
    出さない。
    """
    dto = use_case.execute(
        family_id=family_id,
        account_id=principal.user_id,
        can_manage=principal.can("family:manage"),
    )
    return _to_family(dto)


@router.patch("/{family_id}", response_model=FamilyDetailResponse)
async def rename_family(
    *,
    family_id: int,
    body: FamilyRenameRequest,
    use_case: RenameFamilyDep,
    principal: FamilyManager,
) -> FamilyDetailResponse:
    """家族名を変える（owner のみ）。"""
    dto = use_case.execute(family_id=family_id, account_id=principal.user_id, name=body.name)
    logger.info("family_renamed", extra={"family_id": family_id})
    return _to_family(dto)


@router.delete("/{family_id}", status_code=status.HTTP_204_NO_CONTENT)
async def dissolve_family(family_id: int, use_case: DissolveFamilyDep, principal: FamilyManager) -> None:
    """家族を解散する（owner のみ。自分以外の参加者がいないこと）。"""
    use_case.execute(family_id=family_id, account_id=principal.user_id)
    logger.info("family_dissolved", extra={"family_id": family_id})


@router.post("/{family_id}/leave", status_code=status.HTTP_204_NO_CONTENT)
async def leave_family(family_id: int, use_case: LeaveFamilyDep, principal: FamilyViewer) -> None:
    """家族から抜ける（親のみ。他に親が残る場合に限る）。

    抜けた後は初期状態と同じで、家族を作り直すことも招待を受け直すこともできる。
    """
    use_case.execute(family_id=family_id, account_id=principal.user_id)
    logger.info("family_left", extra={"family_id": family_id})


@router.post(
    "/{family_id}/memberships",
    status_code=status.HTTP_201_CREATED,
    response_model=MembershipResponse,
)
async def add_child(
    *,
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
    *,
    family_id: int,
    membership_id: int,
    use_case: RemoveMembershipDep,
    principal: FamilyManager,
) -> None:
    use_case.execute(family_id=family_id, membership_id=membership_id, account_id=principal.user_id)
    logger.info("membership_removed", extra={"family_id": family_id, "membership_id": membership_id})


@router.put("/{family_id}/member-order", response_model=FamilyDetailResponse)
async def reorder_members(
    *,
    family_id: int,
    body: MemberOrderRequest,
    use_case: ReorderMembersDep,
    principal: FamilyManager,
) -> FamilyDetailResponse:
    """子を並べる順を決める（親メンバー）。

    ナビゲーションもダッシュボードもこの順で並ぶ。並びは家族に 1 つで、誰が
    見ても同じ順になる。
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
async def reset_child_password(
    *,
    family_id: int,
    membership_id: int,
    use_case: ResetChildPasswordDep,
    principal: FamilyManager,
) -> TemporaryPasswordResponse:
    """子の一時パスワードを発行する（ADR-0011）。

    発行の事実は構造化ログと ``log`` テーブルに残る。平文はこの応答でだけ返す。
    """
    dto = use_case.execute(family_id=family_id, membership_id=membership_id, account_id=principal.user_id)
    # 発行の事実（発行者・対象・日時）を残す。平文のパスワードは載せない（ADR-0011）。
    # 発行者は user.id_hash（PII を残さない識別子）としてリクエストログにも付く。
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


# --- 独立（ADR-0014） --------------------------------------------------------


@router.post(
    "/{family_id}/memberships/{membership_id}/independence-proposal",
    response_model=MembershipResponse,
)
async def propose_independence(
    *,
    family_id: int,
    membership_id: int,
    use_case: ProposeIndependenceDep,
    principal: FamilyManager,
) -> MembershipResponse:
    """子の独立を指示する（親メンバー）。子本人が承認した時点で独立が成立する。"""
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
async def revoke_independence_proposal(
    *,
    family_id: int,
    membership_id: int,
    use_case: RevokeIndependenceDep,
    principal: FamilyManager,
) -> None:
    """独立の指示を取り下げる（承認前ならいつでも）。"""
    use_case.execute(family_id=family_id, membership_id=membership_id, account_id=principal.user_id)
    logger.info("independence_proposal_revoked", extra={"family_id": family_id, "membership_id": membership_id})


@router.post("/{family_id}/independence", status_code=status.HTTP_204_NO_CONTENT)
async def approve_independence(
    family_id: int,
    use_case: ApproveIndependenceDep,
    principal: FamilyViewer,
) -> None:
    """独立を承認する（指示を受けた子本人）。

    成立すると参加・台帳・記録は家族から消え、所属なしのメンバーとなる
    （家族を作ることも、招待を受け直すこともできる）。
    """
    use_case.execute(family_id=family_id, account_id=principal.user_id)
    logger.info("independence_approved", extra={"family_id": family_id})


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
async def revoke_invitation(
    *,
    family_id: int,
    invitation_id: int,
    use_case: RevokeInvitationDep,
    principal: FamilyManager,
) -> None:
    use_case.execute(family_id=family_id, invitation_id=invitation_id, account_id=principal.user_id)
    logger.info("invitation_revoked", extra={"family_id": family_id})


# --- 台帳 --------------------------------------------------------------------


@router.get("/{family_id}/reason-suggestions", response_model=list[str])
async def suggest_reasons(family_id: int, use_case: SuggestReasonsDep, principal: PointManager) -> list[str]:
    """その家族でよく使われている理由（入力候補）。頻度の高い順。"""
    return use_case.execute(family_id=family_id, account_id=principal.user_id)


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
    *,
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
    *,
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


@router.post(
    "/{family_id}/ledgers/{ledger_id}/transactions/{transaction_id}/corrections",
    status_code=status.HTTP_201_CREATED,
    response_model=CorrectionResponse,
)
async def correct_transaction(
    *,
    ledger_id: int,
    transaction_id: int,
    body: CorrectionCreateRequest,
    use_case: CorrectTransactionDep,
    principal: PointManager,
) -> CorrectionResponse:
    """入力の間違いを直す。元のレコードは書き換えず、打ち消しと正しい内容の
    2 行を足す（ADR-0022）。

    ``occurred_at`` を省くと、元のレコードの発生日時を引き継ぐ。すでに打ち消し
    済みのレコードは訂正できない（409）。
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
