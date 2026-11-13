"""Permission code list API (requires ``permission:manage``).

The source of truth for permission codes is ``shared/domain/auth/master_data.py``. Codes are
added and removed via master data + migrations, so this API is read-only.
"""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.orm import Session

from presentation.fastapi.dependencies.auth import require_permission
from presentation.fastapi.schemas.admin import PermissionResponse
from shared.infrastructure.models import Permission
from shared.kernel.database.session import get_db

router = APIRouter(
    prefix="/api/admin/permissions",
    tags=["admin"],
    dependencies=[Depends(require_permission("permission:manage"))],
)


@router.get("", response_model=list[PermissionResponse])
def list_permissions(
    db: Annotated[Session, Depends(get_db)],
) -> list[PermissionResponse]:
    permissions = db.scalars(select(Permission).order_by(Permission.code)).all()
    return [PermissionResponse(id=p.id, code=p.code) for p in permissions]
