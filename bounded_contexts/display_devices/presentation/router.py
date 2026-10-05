"""表示端末（サイネージ）の API（ADR-0047）。

端末の側（認証なし）:

- ``POST /api/display/pairings`` ——ペアリングを始める（確認コードと端末の秘密）
- ``POST /api/display/pairings/claim`` ——承認されたら端末の資格情報を 1 度だけ受け取る
- ``POST /api/display/session`` ——端末の資格情報を 5 分のアクセストークンに換える

運用管理者の側（``display:approve``）:

- ``POST /api/display/pairings/approve`` ——映す家族と名前を決めて承認する
- ``GET /api/display/families`` ——映す先として選べる家族
- ``GET /api/display/devices`` / ``DELETE /api/display/devices/{account_id}`` ——一覧と、外す

表示アカウントそのもの（家族の参加・アカウント）は reward_points が持つ。ここは
reward_points の名簿（:class:`DisplayRoster`）と、ペアリング・資格情報をつなぐ。
承認・外す・失効は、どの家族のどの端末かを監査ログへ残す（識別子は本文に入れる。
``log`` テーブルへ入るのは本文だけ）。
"""

from __future__ import annotations

import logging
from datetime import datetime
from typing import Annotated

from fastapi import APIRouter, Depends, Response, status
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session

from bounded_contexts.display_devices.domain.exceptions import (
    DeviceCredentialExpiredError,
    InvalidDeviceCredentialError,
)
from bounded_contexts.display_devices.presentation.dependencies import (
    ApprovePairingDep,
    ClaimPairingDep,
    DescribeDisplayCredentialsDep,
    OpenDisplaySessionDep,
    StartPairingDep,
)
from bounded_contexts.display_devices.presentation.schemas import (
    DisplayableFamilyResponse,
    DisplayDeviceResponse,
    DisplaySessionRequest,
    DisplaySessionResponse,
    PairingApproveRequest,
    PairingClaimRequest,
    PairingClaimResponse,
    PairingStartResponse,
)
from bounded_contexts.reward_points.application.dto.display_dto import DisplayDTO
from bounded_contexts.reward_points.application.use_cases.manage_displays import AttachDisplayCommand
from bounded_contexts.reward_points.presentation.dependencies import DisplayRosterDep
from presentation.fastapi.dependencies.auth import require_permission, set_access_token_cookie
from presentation.fastapi.services.token_service import TokenService
from shared.application.authenticated_principal import AuthenticatedPrincipal
from shared.kernel.database.session import get_db

router = APIRouter(prefix="/api/display", tags=["display"])
logger = logging.getLogger(__name__)

DbDep = Annotated[Session, Depends(get_db)]
# 表示端末を承認する・一覧を見る・外す。運用管理者だけが持つ（ADR-0047）
DisplayApprover = Annotated[AuthenticatedPrincipal, Depends(require_permission("display:approve"))]


# --- 端末の側（認証なし） ---------------------------------------------------


@router.post("/pairings", status_code=status.HTTP_201_CREATED, response_model=PairingStartResponse)
async def start_pairing(use_case: StartPairingDep) -> PairingStartResponse:
    """ペアリングを始める。確認コードを画面に出し、端末の秘密で受け取りを問い合わせる。"""
    started = use_case.execute()
    return PairingStartResponse(
        user_code=started.user_code,
        device_code=started.device_code,
        expires_in=started.expires_in,
        interval=started.interval,
    )


@router.post("/pairings/claim", response_model=PairingClaimResponse)
async def claim_pairing(body: PairingClaimRequest, use_case: ClaimPairingDep) -> PairingClaimResponse:
    """承認されていれば、端末の資格情報を 1 度だけ返す。

    まだなら 400 ``authorization_pending``（間隔を空けて問い合わせ続ける）、期限切れ・
    受け取り済みなら 400 ``expired_token``（ペアリングをやり直す）。RFC 8628 §3.5。
    """
    return PairingClaimResponse(device_credential=use_case.execute(body.device_code))


@router.post("/session", response_model=DisplaySessionResponse)
async def open_session(
    *,
    body: DisplaySessionRequest,
    response: Response,
    use_case: OpenDisplaySessionDep,
    roster: DisplayRosterDep,
    db: DbDep,
) -> DisplaySessionResponse | JSONResponse:
    """端末の資格情報を、5 分のアクセストークンに換える（リフレッシュトークンは出さない）。

    ⚠ **毎回 DB を引く**（ADR-0037）。外された端末・止められたアカウント・家族から
    外れた端末は 401 で、端末はペアリングの画面へ戻る。
    """
    try:
        account_id = use_case.execute(body.device_credential)
    except DeviceCredentialExpiredError as error:
        # ⚠ 例外で抜けると外した結果まで巻き戻るので、応答を組み立てて返す
        detached = roster.detach(error.account_id)
        logger.info("display_expired: family_id=%s account_id=%s", detached.family_id, detached.account_id)
        return _unauthorized(error.code)
    user = TokenService.load_active_user(account_id, session=db)
    if user is None or roster.find(account_id) is None:
        raise InvalidDeviceCredentialError
    issued = TokenService.create_display_access_token(user)
    access_token = str(issued["access_token"])
    set_access_token_cookie(response, access_token)
    return DisplaySessionResponse(access_token=access_token, expires_in=int(str(issued["expires_in"])))


def _unauthorized(code: str) -> JSONResponse:
    return JSONResponse(status_code=status.HTTP_401_UNAUTHORIZED, content={"detail": {"error": code}})


# --- 運用管理者の側（display:approve） --------------------------------------


@router.post("/pairings/approve", status_code=status.HTTP_201_CREATED, response_model=DisplayDeviceResponse)
async def approve_pairing(
    *,
    body: PairingApproveRequest,
    use_case: ApprovePairingDep,
    roster: DisplayRosterDep,
    principal: DisplayApprover,
) -> DisplayDeviceResponse:
    """確認コードを承認し、映す家族へ表示端末を加える。

    確認コードが無い・承認済みなら 404 ``pairing_not_found``、期限切れなら 410
    ``pairing_expired``。どちらのときも表示アカウントは作らない。
    """
    attached: list[DisplayDTO] = []

    def enroll() -> int:
        display = roster.attach(AttachDisplayCommand(family_id=body.family_id, name=body.name))
        attached.append(display)
        return display.account_id

    use_case.execute(user_code=body.user_code, enroll=enroll)
    display = attached[0]
    logger.info(
        "display_approved: family_id=%s account_id=%s approver_id=%s",
        display.family_id,
        display.account_id,
        principal.user_id,
    )
    return _to_device(display, last_used_at=None)


@router.get("/families", response_model=list[DisplayableFamilyResponse])
async def list_families(roster: DisplayRosterDep, _principal: DisplayApprover) -> list[DisplayableFamilyResponse]:
    """映す先として選べる家族（名前だけ。台帳は載せない）。"""
    return [DisplayableFamilyResponse(id=family.id, name=family.name) for family in roster.families_to_display()]


@router.get("/devices", response_model=list[DisplayDeviceResponse])
async def list_devices(
    roster: DisplayRosterDep, credentials: DescribeDisplayCredentialsDep, _principal: DisplayApprover
) -> list[DisplayDeviceResponse]:
    """全ての家族の表示端末と、最後に使った日時。"""
    last_used = credentials.last_used()
    return [_to_device(display, last_used_at=last_used.get(display.account_id)) for display in roster.list_all()]


@router.delete("/devices/{account_id}", status_code=status.HTTP_204_NO_CONTENT)
async def remove_device(account_id: int, roster: DisplayRosterDep, principal: DisplayApprover) -> None:
    """表示端末を外す。参加・アカウント・資格情報を消す。

    ⚠ 端末の手元のアクセストークンは寿命（5 分）まで通る（ADR-0037 と同じ上限）。
    """
    detached = roster.detach(account_id)
    logger.info(
        "display_removed: family_id=%s account_id=%s remover_id=%s",
        detached.family_id,
        detached.account_id,
        principal.user_id,
    )


def _to_device(display: DisplayDTO, *, last_used_at: datetime | None) -> DisplayDeviceResponse:
    return DisplayDeviceResponse(
        account_id=display.account_id,
        family_id=display.family_id,
        family_name=display.family_name,
        name=display.name,
        created_at=display.created_at,
        last_used_at=last_used_at,
    )


__all__ = ["router"]
