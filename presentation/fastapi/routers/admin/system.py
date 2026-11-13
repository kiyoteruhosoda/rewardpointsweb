"""Application restart API (requires ``system:manage``).

Accepts restart requests so that settings only read at startup (logging, CORS, etc.) can be
applied from the admin console. Requests are stored in the DB; each process decides whether
one is meant for it and exits itself. Coming back up is left to the container's restart policy
(:mod:`shared.kernel.restart`).
"""

from __future__ import annotations

import logging
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from presentation.fastapi.dependencies.auth import require_permission
from presentation.fastapi.schemas.admin import (
    RestartCommandRequest,
    RestartCommandResponse,
    RestartRequestResponse,
    RestartStatusResponse,
)
from shared.application.authenticated_principal import AuthenticatedPrincipal
from shared.kernel.database.session import get_db
from shared.kernel.restart import (
    ALL_RESTART_SCOPES,
    RestartRequest,
    RestartRequestStore,
    RestartScope,
)
from shared.kernel.timestamps import isoformat_utc

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/admin/system", tags=["admin"])

DbDep = Annotated[Session, Depends(get_db)]
SystemManagerDep = Annotated[AuthenticatedPrincipal, Depends(require_permission("system:manage"))]


def _to_response(request: RestartRequest) -> RestartRequestResponse:
    return RestartRequestResponse(
        scope=request.scope.value,
        token=request.token,
        requested_at=(isoformat_utc(request.requested_at) if request.requested_at else None),
        requested_by=request.requested_by,
        reason=request.reason,
    )


@router.get("/restart", response_model=RestartStatusResponse)
async def restart_status(_principal: SystemManagerDep) -> RestartStatusResponse:
    """Return the latest restart request per scope and the list of scopes that can be specified."""
    stored = RestartRequestStore().load_all()
    return RestartStatusResponse(
        available_scopes=[scope.value for scope in ALL_RESTART_SCOPES],
        last_requests=[_to_response(stored[scope]) for scope in ALL_RESTART_SCOPES if scope in stored],
    )


@router.post(
    "/restart",
    response_model=RestartCommandResponse,
    status_code=status.HTTP_202_ACCEPTED,
)
def request_restart(
    body: RestartCommandRequest,
    principal: SystemManagerDep,
    db: DbDep,
) -> RestartCommandResponse:
    """Request a restart.

    If ``scopes`` is omitted, all services are targeted. A watcher thread picks up and
    handles the request, so nothing has restarted yet when the response returns.
    """
    if body.scopes is None:
        scopes: tuple[RestartScope, ...] = ALL_RESTART_SCOPES
    else:
        scopes = RestartScope.parse_all(body.scopes)
        if not scopes:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail={"error": "invalid_restart_scope"},
            )

    reason = body.reason.strip() if body.reason and body.reason.strip() else None
    try:
        requests = RestartRequestStore().save(
            db,
            scopes,
            # The requester also ends up in logs, so record a principal identifier without PII
            requested_by=f"user:{principal.user_id}",
            reason=reason,
        )
    except Exception:
        logger.exception("Failed to save the restart request")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={"error": "restart_request_failed"},
        ) from None

    return RestartCommandResponse(requested=True, requests=[_to_response(request) for request in requests])
