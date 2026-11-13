"""System settings API (requires ``admin:system-settings``).

Saves are recorded in the app log. They change behavior, and without being able to trace
"when did the setting change" later, incidents cannot be narrowed down. **Only key names are
logged**: values include secrets (``MAIL_PASSWORD`` etc.) (CLAUDE.md "Logging").
"""

from __future__ import annotations

import logging
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from bounded_contexts.account_security.domain.exceptions import (
    PasskeyConfigurationError,
)
from presentation.fastapi.dependencies.auth import require_permission
from presentation.fastapi.schemas.admin import (
    RestartRequirementResponse,
    SystemSettingItemResponse,
    SystemSettingsUpdateRequest,
    SystemSettingsUpdateResponse,
)
from presentation.fastapi.services.system_setting_service import SettingRefusedError, SystemSettingService
from shared.kernel.database.session import get_db

logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/api/admin/config",
    tags=["admin"],
    dependencies=[Depends(require_permission("admin:system-settings"))],
)

DbDep = Annotated[Session, Depends(get_db)]


@router.get("", response_model=list[SystemSettingItemResponse])
def get_config(db: DbDep) -> list[SystemSettingItemResponse]:
    return [SystemSettingItemResponse(**item) for item in SystemSettingService.effective_config(db)]


@router.put("", response_model=SystemSettingsUpdateResponse)
def update_config(body: SystemSettingsUpdateRequest, db: DbDep) -> SystemSettingsUpdateResponse:
    """Save the settings.

    Returns ``restart_required`` when a setting that is only read at startup changed.
    The actual restart is requested with ``POST /api/admin/system/restart``.
    """
    try:
        saved = SystemSettingService.save(db, body.values)
    except SettingRefusedError as refused:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"error": refused.error, "key": refused.key},
        ) from refused
    except PasskeyConfigurationError as error:
        # The default handler returns 500 as "server misconfiguration". Here it is an error
        # in the value the admin is entering right now, so return it as an input error.
        logger.info("system_settings_rejected: %s", error.code)
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail={"error": error.code}) from error
    # Log only the keys actually applied. Using the requested keys would count unknown keys
    # and still-masked secrets (neither is saved) as "changed".
    logger.info("system_settings_updated: keys=%s", ",".join(saved.accepted_keys) or "none")
    return SystemSettingsUpdateResponse(
        status="ok",
        restart_required=(
            RestartRequirementResponse(
                scopes=[scope.value for scope in saved.restart.scopes],
                keys=list(saved.restart.keys),
            )
            if saved.restart
            else None
        ),
    )
