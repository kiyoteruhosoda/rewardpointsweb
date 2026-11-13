"""API for display devices (signage) (ADR-0047).

Device side (no authentication):

- ``POST /api/display/pairings`` -- start pairing (confirmation code and device secret)
- ``POST /api/display/pairings/claim`` -- once approved, receive the device credential exactly once
- ``POST /api/display/session`` -- exchange the device credential for a 5-minute access token

Operations admin side (``display:approve``; only for families where they are owner / parent; task #758):

- ``POST /api/display/pairings/approve`` -- approve, choosing the family to show and a name
- ``GET /api/display/families`` -- families that can be chosen as the target
- ``GET /api/display/devices`` / ``DELETE /api/display/devices/{account_id}`` -- list, and remove

The display account itself (family membership, account) is owned by reward_points. This module
connects the reward_points roster (:class:`DisplayRoster`) with pairing and credentials.
Approvals, removals and revocations record which device of which family in the audit log (the
identifiers go into the message text; only the message text goes into the ``log`` table).
"""

from __future__ import annotations

import logging
from datetime import datetime
from typing import Annotated

from fastapi import APIRouter, Depends, Response, status
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session

from bounded_contexts.account_security.presentation.qr_code import render_qr_code_data_uri
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
    PairingStartRequest,
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
# The approval screen (frontend). The QR code points here
APPROVE_PATH = "/admin/displays/approve"
logger = logging.getLogger(__name__)

DbDep = Annotated[Session, Depends(get_db)]
# Approve, list and remove display devices. Held only by operations admins (ADR-0047)
DisplayApprover = Annotated[AuthenticatedPrincipal, Depends(require_permission("display:approve"))]


# --- Device side (no authentication) -------------------------------------


@router.post("/pairings", status_code=status.HTTP_201_CREATED, response_model=PairingStartResponse)
def start_pairing(use_case: StartPairingDep, body: PairingStartRequest | None = None) -> PairingStartResponse:
    """Start pairing. Show the confirmation code on screen; poll for the claim with the device secret.

    When ``origin`` is sent, also return a QR code pointing at the approval screen. The confirmation
    code goes after the ``#`` in the URL (same reason as ADR-0025: keep it out of server logs and Referer).
    """
    started = use_case.execute()
    origin = body.origin if body is not None else None
    return PairingStartResponse(
        user_code=started.user_code,
        device_code=started.device_code,
        expires_in=started.expires_in,
        interval=started.interval,
        qr_code=None if origin is None else render_qr_code_data_uri(f"{origin}{APPROVE_PATH}#{started.user_code}"),
    )


@router.post("/pairings/claim", response_model=PairingClaimResponse)
def claim_pairing(body: PairingClaimRequest, use_case: ClaimPairingDep) -> PairingClaimResponse:
    """If approved, return the device credential exactly once.

    If not yet approved, 400 ``authorization_pending`` (keep polling at the interval); if expired or
    already claimed, 400 ``expired_token`` (start pairing again). RFC 8628 §3.5.
    """
    return PairingClaimResponse(device_credential=use_case.execute(body.device_code))


@router.post("/session", response_model=DisplaySessionResponse)
def open_session(
    *,
    body: DisplaySessionRequest,
    response: Response,
    use_case: OpenDisplaySessionDep,
    roster: DisplayRosterDep,
    db: DbDep,
) -> DisplaySessionResponse | JSONResponse:
    """Exchange the device credential for a 5-minute access token (no refresh token is issued).

    ⚠ **Hits the DB every time** (ADR-0037). A removed device, a disabled account, or a device
    no longer in the family gets 401, and the device goes back to the pairing screen.
    """
    try:
        account_id = use_case.execute(body.device_credential)
    except DeviceCredentialExpiredError as error:
        # ⚠ Leaving via an exception would roll back the removal too, so build and return a response
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


# --- Operations admin side (display:approve) ------------------------------


@router.post("/pairings/approve", status_code=status.HTTP_201_CREATED, response_model=DisplayDeviceResponse)
def approve_pairing(
    *,
    body: PairingApproveRequest,
    use_case: ApprovePairingDep,
    roster: DisplayRosterDep,
    principal: DisplayApprover,
) -> DisplayDeviceResponse:
    """Approve the confirmation code and add the display device to the family to show.

    If the confirmation code does not exist or is already approved, 404 ``pairing_not_found``; if
    expired, 410 ``pairing_expired``. If the approver is not owner / parent of the family, 403
    ``family_access_denied`` (task #758). In none of these cases is a display account created.
    """
    attached: list[DisplayDTO] = []

    def enroll() -> int:
        display = roster.attach(
            AttachDisplayCommand(family_id=body.family_id, name=body.name, approver_id=principal.user_id)
        )
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
def list_families(roster: DisplayRosterDep, principal: DisplayApprover) -> list[DisplayableFamilyResponse]:
    """Families selectable as the target (names only, no ledger). Only those where the approver is owner / parent."""
    return [
        DisplayableFamilyResponse(id=family.id, name=family.name)
        for family in roster.families_to_display(principal.user_id)
    ]


@router.get("/devices", response_model=list[DisplayDeviceResponse])
def list_devices(
    roster: DisplayRosterDep, credentials: DescribeDisplayCredentialsDep, _principal: DisplayApprover
) -> list[DisplayDeviceResponse]:
    """Display devices of all families, with when each was last used."""
    last_used = credentials.last_used()
    return [_to_device(display, last_used_at=last_used.get(display.account_id)) for display in roster.list_all()]


@router.delete("/devices/{account_id}", status_code=status.HTTP_204_NO_CONTENT)
def remove_device(account_id: int, roster: DisplayRosterDep, principal: DisplayApprover) -> None:
    """Remove a display device. Deletes the membership, account and credential.

    ⚠ The access token already on the device keeps working until it expires (5 min; same limit as ADR-0037).
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
