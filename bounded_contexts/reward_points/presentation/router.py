"""reward_points コンテキストの API。

認可は 2 段構えになっている。

1. **scope**（``member:view`` / ``point:manage`` 等）— その操作を行える立場か
2. **メンバーごとのアクセス**（所有・共有・本人）— *その* メンバーを触れるか

1 はここで宣言し、2 は Application 層の
:class:`~bounded_contexts.reward_points.application.member_access_resolver.MemberAccessResolver`
が判定する。``point:manage`` を持つ管理者でも、共有されていないメンバーは触れない。
"""

from __future__ import annotations

import logging
from typing import Annotated

from fastapi import APIRouter, Depends, status

from bounded_contexts.reward_points.application.dto.member_dto import (
    MemberDetailDTO,
    MemberShareDTO,
    MemberSummaryDTO,
)
from bounded_contexts.reward_points.application.dto.point_entry_dto import PointEntryDTO
from bounded_contexts.reward_points.application.use_cases.record_point_addition import (
    RecordPointAdditionCommand,
)
from bounded_contexts.reward_points.application.use_cases.record_point_consumption import (
    RecordPointConsumptionCommand,
)
from bounded_contexts.reward_points.application.use_cases.register_member import RegisterMemberCommand
from bounded_contexts.reward_points.application.use_cases.share_member import ShareMemberCommand
from bounded_contexts.reward_points.presentation.dependencies import (
    DeleteEntryDep,
    DeleteMemberDep,
    ListMembersDep,
    ListSharesDep,
    RecordAdditionDep,
    RecordConsumptionDep,
    RegisterMemberDep,
    RevokeShareDep,
    ShareMemberDep,
    ViewLedgerDep,
)
from bounded_contexts.reward_points.presentation.schemas import (
    MemberCreateRequest,
    MemberResponse,
    MemberShareRequest,
    MemberShareResponse,
    MemberSummaryResponse,
    PointAdditionRequest,
    PointConsumptionRequest,
    PointEntryResponse,
    PointLedgerResponse,
)
from presentation.fastapi.dependencies.auth import require_permission
from shared.application.authenticated_principal import AuthenticatedPrincipal

router = APIRouter(prefix="/api/members", tags=["reward-points"])
logger = logging.getLogger(__name__)

MemberViewer = Annotated[AuthenticatedPrincipal, Depends(require_permission("member:view"))]
MemberManager = Annotated[AuthenticatedPrincipal, Depends(require_permission("member:manage"))]
PointViewer = Annotated[AuthenticatedPrincipal, Depends(require_permission("point:view"))]
PointManager = Annotated[AuthenticatedPrincipal, Depends(require_permission("point:manage"))]


def _to_summary(dto: MemberSummaryDTO) -> MemberSummaryResponse:
    return MemberSummaryResponse(
        id=dto.id,
        name=dto.name,
        balance=dto.balance,
        access_level=dto.access_level,
        is_self=dto.is_self,
        is_owner=dto.is_owner,
        has_linked_user=dto.has_linked_user,
    )


def _to_member(dto: MemberDetailDTO) -> MemberResponse:
    return MemberResponse(
        id=dto.id,
        name=dto.name,
        balance=dto.balance,
        access_level=dto.access_level,
        is_self=dto.is_self,
        is_owner=dto.is_owner,
        linked_user_email=dto.linked_user_email,
    )


def _to_entry(dto: PointEntryDTO) -> PointEntryResponse:
    return PointEntryResponse(
        id=dto.id,
        entry_type=dto.entry_type,
        occurred_at=dto.occurred_at,
        points=dto.points,
        signed_points=dto.signed_points,
        description=dto.description,
    )


def _to_share(dto: MemberShareDTO) -> MemberShareResponse:
    return MemberShareResponse(
        user_id=dto.user_id,
        email=dto.email,
        username=dto.username,
        access_level=dto.access_level,
    )


# --- メンバー ----------------------------------------------------------------


@router.get("", response_model=list[MemberSummaryResponse])
async def list_members(use_case: ListMembersDep, principal: MemberViewer) -> list[MemberSummaryResponse]:
    """自分が見られるメンバー（所有・共有・本人）を返す。"""
    return [_to_summary(dto) for dto in use_case.execute(principal.user_id)]


@router.post("", status_code=status.HTTP_201_CREATED, response_model=MemberResponse)
async def create_member(
    body: MemberCreateRequest, use_case: RegisterMemberDep, principal: MemberManager
) -> MemberResponse:
    dto = use_case.execute(
        RegisterMemberCommand(
            name=body.name,
            owner_user_id=principal.user_id,
            linked_user_email=str(body.linked_user_email) if body.linked_user_email else None,
        )
    )
    logger.info("member_registered", extra={"member_id": dto.id})
    return _to_member(dto)


@router.delete("/{member_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_member(member_id: int, use_case: DeleteMemberDep, principal: MemberManager) -> None:
    use_case.execute(member_id=member_id, user_id=principal.user_id)
    logger.info("member_deleted", extra={"member_id": member_id})


# --- ポイント ----------------------------------------------------------------


@router.get("/{member_id}/points", response_model=PointLedgerResponse)
async def view_points(member_id: int, use_case: ViewLedgerDep, principal: PointViewer) -> PointLedgerResponse:
    """残高と履歴。``access_level`` で画面側が変更 UI の出し分けを決める。"""
    dto = use_case.execute(member_id=member_id, user_id=principal.user_id)
    return PointLedgerResponse(
        member_id=dto.member_id,
        member_name=dto.member_name,
        balance=dto.balance,
        access_level=dto.access_level,
        is_owner=dto.is_owner,
        entries=[_to_entry(entry) for entry in dto.entries],
    )


@router.post(
    "/{member_id}/points/additions",
    status_code=status.HTTP_201_CREATED,
    response_model=PointEntryResponse,
)
async def add_points(
    member_id: int,
    body: PointAdditionRequest,
    use_case: RecordAdditionDep,
    principal: PointManager,
) -> PointEntryResponse:
    dto = use_case.execute(
        RecordPointAdditionCommand(
            member_id=member_id,
            user_id=principal.user_id,
            points=body.points,
            reason=body.reason,
            occurred_at=body.occurred_at,
        )
    )
    logger.info("points_added", extra={"member_id": member_id, "points": dto.points})
    return _to_entry(dto)


@router.post(
    "/{member_id}/points/consumptions",
    status_code=status.HTTP_201_CREATED,
    response_model=PointEntryResponse,
)
async def consume_points(
    member_id: int,
    body: PointConsumptionRequest,
    use_case: RecordConsumptionDep,
    principal: PointManager,
) -> PointEntryResponse:
    dto = use_case.execute(
        RecordPointConsumptionCommand(
            member_id=member_id,
            user_id=principal.user_id,
            points=body.points,
            application=body.application,
            occurred_at=body.occurred_at,
        )
    )
    logger.info("points_consumed", extra={"member_id": member_id, "points": dto.points})
    return _to_entry(dto)


@router.delete("/{member_id}/points/{entry_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_point_entry(member_id: int, entry_id: int, use_case: DeleteEntryDep, principal: PointManager) -> None:
    use_case.execute(member_id=member_id, entry_id=entry_id, user_id=principal.user_id)
    logger.info("point_entry_deleted", extra={"member_id": member_id, "entry_id": entry_id})


# --- 共有 --------------------------------------------------------------------


@router.get("/{member_id}/shares", response_model=list[MemberShareResponse])
async def list_shares(member_id: int, use_case: ListSharesDep, principal: MemberManager) -> list[MemberShareResponse]:
    dtos = use_case.execute(member_id=member_id, user_id=principal.user_id)
    return [_to_share(dto) for dto in dtos]


@router.post(
    "/{member_id}/shares",
    status_code=status.HTTP_201_CREATED,
    response_model=MemberShareResponse,
)
async def share_member(
    member_id: int,
    body: MemberShareRequest,
    use_case: ShareMemberDep,
    principal: MemberManager,
) -> MemberShareResponse:
    dto = use_case.execute(
        ShareMemberCommand(
            member_id=member_id,
            user_id=principal.user_id,
            target_email=str(body.email),
            access_level=body.access_level,
        )
    )
    logger.info("member_shared", extra={"member_id": member_id, "access_level": dto.access_level.value})
    return _to_share(dto)


@router.delete("/{member_id}/shares/{target_user_id}", status_code=status.HTTP_204_NO_CONTENT)
async def revoke_share(member_id: int, target_user_id: int, use_case: RevokeShareDep, principal: MemberManager) -> None:
    use_case.execute(member_id=member_id, target_user_id=target_user_id, user_id=principal.user_id)
    logger.info("member_share_revoked", extra={"member_id": member_id})
