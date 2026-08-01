"""システム設定 API（要 ``admin:system-settings``）。

保存はアプリログへ残す。挙動が変わる操作で、後から「いつ設定が変わったか」を
追えないと障害の切り分けができない。**残すのはキー名だけ**——値には秘匿項目
（``MAIL_PASSWORD`` 等）が含まれる（CLAUDE.md「ログ」）。
"""

from __future__ import annotations

import logging
from typing import Annotated

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from presentation.fastapi.dependencies.auth import require_permission
from presentation.fastapi.schemas.admin import (
    RestartRequirementResponse,
    SystemSettingItemResponse,
    SystemSettingsUpdateRequest,
    SystemSettingsUpdateResponse,
)
from presentation.fastapi.services.system_setting_service import SystemSettingService
from shared.kernel.database.session import get_db

logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/api/admin/config",
    tags=["admin"],
    dependencies=[Depends(require_permission("admin:system-settings"))],
)

DbDep = Annotated[Session, Depends(get_db)]


@router.get("", response_model=list[SystemSettingItemResponse])
async def get_config(db: DbDep) -> list[SystemSettingItemResponse]:
    return [SystemSettingItemResponse(**item) for item in SystemSettingService.effective_config(db)]


@router.put("", response_model=SystemSettingsUpdateResponse)
async def update_config(body: SystemSettingsUpdateRequest, db: DbDep) -> SystemSettingsUpdateResponse:
    """設定を保存する。

    起動時にしか読まれない設定を変更した場合は ``restart_required`` を返す。
    実際の再起動は ``POST /api/admin/system/restart`` で要求する。
    """
    saved = SystemSettingService.save(db, body.values)
    # 実際に採り込んだキーだけを残す。要求されたキーを使うと、未知のキーや伏せ字の
    # ままの秘匿項目（どちらも保存されない）まで「変更した」ことになってしまう。
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
