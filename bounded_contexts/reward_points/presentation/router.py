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
# 家族の作成は「一人前の保護者」になる操作なので、保護者の scope 一式を要求する。
# 一部しか持たないカスタムロールが、閲覧も記録もできない owner を生まないため
FamilyGuardian = Annotated[
    AuthenticatedPrincipal,
    Depends(require_permission("family:view", "family:manage", "point:view", "point:manage")),
]
# 控えには家族の全部（子どもの台帳と履歴）が載るので、家族と台帳の両方を
# 見られる立場を要求する（ADR-0026）。どの家族を書き出せるかは、この先で
# 家族の中での立場が決める
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


# --- 控え（バックアップ。ADR-0026） ------------------------------------------


@router.post("/import", status_code=status.HTTP_201_CREATED, response_model=ImportedFamilyResponse)
async def import_family(
    body: FamilyArchiveDocument, use_case: ImportFamilyDep, principal: FamilyGuardian
) -> ImportedFamilyResponse:
    """控えから家族を作り直す（復元）。

    作られるのは **新しい家族** で、呼んだ人が owner になる。既存の家族へ混ぜる
    ことはできないので、どこかに所属したままでは呼べない（``already_belongs_to_family``）。

    owner 以外の参加者はアカウント未紐付けで戻る。本人が入り直す道は招待コード。
    子の台帳は記録ごと戻るので、招待を受けた子には自分の履歴が残っている。
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
async def export_family(family_id: int, use_case: ExportFamilyDep, principal: ArchiveReader) -> FamilyArchiveDocument:
    """家族まるごとを控えとして書き出す（親のみ）。

    参加者・子どもの台帳・記録・毎日のボーナスが 1 つの JSON に入る。**アカウント
    は入らない** — ログイン ID もパスワードも招待コードも載らないので、この控えから
    誰かのアカウントを乗っ取ることはできない。

    そのまま ``POST /api/families/import`` へ送れば元に戻る。
    """
    archive = use_case.execute(family_id=family_id, account_id=principal.user_id)
    logger.info("family_exported", extra={"family_id": family_id, "member_count": len(archive.members)})
    return family_archive_documents.to_document(archive)


# --- 家族（続き） ------------------------------------------------------------


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


@router.put("/{family_id}/rules", response_model=FamilyDetailResponse)
async def edit_family_rules(
    *,
    family_id: int,
    body: FamilyRulesRequest,
    use_case: EditFamilyRulesDep,
    principal: FamilyManager,
) -> FamilyDetailResponse:
    """家族で決めた約束ごと（ルール）を書き換える（親メンバー。ADR-0027）。

    家族に 1 つで、参加している全員が同じ文面を読む。ポイントの付与は変わらない
    — 何を約束したかを書き留めるだけで、量を決めるのは親の記録と毎日のボーナス。

    ``rules`` を省く（``null``）か空にすると、書いてあったルールを消す。
    """
    dto = use_case.execute(family_id=family_id, account_id=principal.user_id, rules=body.rules)
    logger.info("family_rules_edited", extra={"family_id": family_id})
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
    display_account_id = use_case.execute(
        family_id=family_id, membership_id=membership_id, account_id=principal.user_id
    )
    if display_account_id is not None:
        # 運用管理者が外したときと同じ本文で残す（誰が・どの家族の・どの端末を。ADR-0047）
        logger.info(
            "display_removed: family_id=%s account_id=%s remover_id=%s",
            family_id,
            display_account_id,
            principal.user_id,
        )
        return
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
        daily_bonus=_to_daily_bonus(dto.daily_bonus) if dto.daily_bonus else None,
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


# --- 毎日のボーナス（ADR-0024） ----------------------------------------------


@router.put("/{family_id}/ledgers/{ledger_id}/daily-bonus", response_model=DailyBonusResponse)
async def configure_daily_bonus(
    *,
    ledger_id: int,
    body: DailyBonusRequest,
    use_case: ConfigureDailyBonusDep,
    principal: PointManager,
) -> DailyBonusResponse:
    """毎日いくつ足すかを決める（すでに決まっていれば書き換える）。

    渡し始めるのは **次に日付が変わったとき** から。この呼び出しでは台帳へ 1 行も
    足さないので、決めた時刻によって受け取り方は変わらない。現在の設定は台帳
    （``GET .../ledgers/{id}``）の ``daily_bonus`` に載る。
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
async def stop_daily_bonus(
    *,
    ledger_id: int,
    use_case: StopDailyBonusDep,
    principal: PointManager,
) -> None:
    """毎日のボーナスをやめる。すでに渡したポイントはそのまま残る。

    設定が無いときも成功する（やめたいという求めはすでに満たされている）。
    """
    use_case.execute(ledger_id=ledger_id, account_id=principal.user_id)
    logger.info("daily_bonus_stopped", extra={"ledger_id": ledger_id})


# --- イベント（ADR-0042） ----------------------------------------------------


def _event_path(suffix: str = "") -> str:
    return "/{family_id}/ledgers/{ledger_id}/events" + suffix


@router.get(_event_path(), response_model=RewardEventBoardResponse)
async def view_reward_events(
    ledger_id: int, use_case: ViewRewardEventsDep, principal: PointViewer
) -> RewardEventBoardResponse:
    """その子のイベント（がんばりカード）を作った順に返す。

    子ども本人も自分のカードを見られる。``can_modify`` が偽なら貼る・作る入口を出さない。
    """
    dto = use_case.execute(ledger_id=ledger_id, account_id=principal.user_id)
    return RewardEventBoardResponse(
        ledger_id=dto.ledger_id,
        display_name=dto.display_name,
        can_modify=dto.can_modify,
        events=[_to_reward_event(event) for event in dto.events],
    )


@router.post(_event_path(), status_code=status.HTTP_201_CREATED, response_model=RewardEventResponse)
async def create_reward_event(
    *,
    ledger_id: int,
    body: RewardEventCreateRequest,
    use_case: CreateRewardEventDep,
    principal: PointManager,
) -> RewardEventResponse:
    """イベントを作る。``goal_count`` だけマスが並び、全部埋まると ``reward_points`` が台帳に入る。

    ``deadline`` を決めると、その日のうちに埋まらなければ期限切れになる（過ぎた日は 400）。
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
async def change_reward_event_deadline(
    *,
    ledger_id: int,
    event_id: int,
    body: RewardEventDeadlineRequest,
    use_case: ChangeRewardEventDeadlineDep,
    principal: PointManager,
) -> RewardEventResponse:
    """期限を決め直す（null で期限なし）。期限切れのカードも、延ばせばまた貼れる。"""
    dto = use_case.execute(
        ChangeDeadlineCommand(
            ledger_id=ledger_id, event_id=event_id, account_id=principal.user_id, deadline=body.deadline
        )
    )
    logger.info("reward_event_deadline_changed", extra={"ledger_id": ledger_id, "event_id": event_id})
    return _to_reward_event(dto)


@router.put(_event_path("/{event_id}/stickers/{number}"), response_model=RewardEventResponse)
async def stick_reward_event_sticker(
    *,
    ledger_id: int,
    event_id: int,
    number: int,
    use_case: StickRewardEventStickerDep,
    principal: PointManager,
) -> RewardEventResponse:
    """*number* 枚目のシールを貼る（1 回達成した）。

    ``number`` は次に貼る番号（今の枚数 + 1）。もう貼ってある番号なら何もせず今の姿を
    返すので、同じ押下を送り直しても 2 枚にはならない。最後のマスが埋まると台帳へ
    ``reward_points`` が足され、``completed_at`` が入る。
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
async def peel_reward_event_sticker(
    *,
    ledger_id: int,
    event_id: int,
    number: int,
    use_case: PeelRewardEventStickerDep,
    principal: PointManager,
) -> RewardEventResponse:
    """最後に貼った 1 枚をはがす（押し間違いを戻す）。達成した後ははがせない。"""
    dto = use_case.execute(
        StickerCommand(ledger_id=ledger_id, event_id=event_id, account_id=principal.user_id, number=number)
    )
    logger.info("reward_event_sticker_peeled", extra={"ledger_id": ledger_id, "event_id": event_id, "number": number})
    return _to_reward_event(dto)


@router.delete(_event_path("/{event_id}"), status_code=status.HTTP_204_NO_CONTENT)
async def delete_reward_event(
    *,
    ledger_id: int,
    event_id: int,
    use_case: DeleteRewardEventDep,
    principal: PointManager,
) -> None:
    """イベントを消す。達成で足したポイントは台帳に残る。"""
    use_case.execute(ledger_id=ledger_id, event_id=event_id, account_id=principal.user_id)
    logger.info("reward_event_deleted", extra={"ledger_id": ledger_id, "event_id": event_id})
