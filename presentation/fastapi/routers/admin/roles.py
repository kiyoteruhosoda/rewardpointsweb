"""Role management API (requires ``role:manage``).

Changes to permission assignments are recorded in the app log (who gained access to what
will always be asked later). IDs and permission codes go in the message text: only columns
reach the ``log`` table, and the rest of ``extra`` appears only in the stdout JSON.
"""

from __future__ import annotations

import logging
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from presentation.fastapi.dependencies.auth import require_permission
from presentation.fastapi.schemas.admin import (
    RoleCreateRequest,
    RoleResponse,
    RoleUpdateRequest,
)
from shared.infrastructure.models import Permission, Role
from shared.kernel.database.session import get_db

logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/api/admin/roles",
    tags=["admin"],
    dependencies=[Depends(require_permission("role:manage"))],
)

DbDep = Annotated[Session, Depends(get_db)]


def _to_response(role: Role) -> RoleResponse:
    return RoleResponse(id=role.id, name=role.name, permissions=sorted(p.code for p in role.permissions))


def _resolve_permissions(db: Session, codes: list[str]) -> list[Permission]:
    permissions = db.scalars(select(Permission).where(Permission.code.in_(codes))).all()
    missing = set(codes) - {p.code for p in permissions}
    if missing:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"error": "unknown_permissions", "permissions": sorted(missing)},
        )
    return list(permissions)


@router.get("", response_model=list[RoleResponse])
def list_roles(db: DbDep) -> list[RoleResponse]:
    roles = db.scalars(select(Role).order_by(Role.id)).all()
    return [_to_response(r) for r in roles]


@router.post("", status_code=status.HTTP_201_CREATED, response_model=RoleResponse)
def create_role(body: RoleCreateRequest, db: DbDep) -> RoleResponse:
    if db.scalar(select(Role).where(Role.name == body.name)):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={"error": "role_already_exists"},
        )
    role = Role(name=body.name)
    role.permissions = _resolve_permissions(db, body.permissions)
    db.add(role)
    db.flush()
    logger.info("admin_role_created: role_id=%s name=%s", role.id, role.name)
    return _to_response(role)


@router.put("/{role_id}", response_model=RoleResponse)
def update_role(role_id: int, body: RoleUpdateRequest, db: DbDep) -> RoleResponse:
    role = db.get(Role, role_id)
    if role is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail={"error": "role_not_found"})
    if body.name is not None:
        role.name = body.name
    if body.permissions is not None:
        role.permissions = _resolve_permissions(db, body.permissions)
    db.flush()
    # Record the permissions as they are after the change. A diff alone cannot later
    # reconstruct what was allowed at that point in time.
    logger.info(
        "admin_role_updated: role_id=%s name=%s permissions=%s",
        role_id,
        role.name,
        ",".join(sorted(p.code for p in role.permissions)),
    )
    return _to_response(role)


@router.delete("/{role_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_role(role_id: int, db: DbDep) -> None:
    role = db.get(Role, role_id)
    if role is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail={"error": "role_not_found"})
    role.permissions = []
    db.delete(role)
    logger.info("admin_role_deleted: role_id=%s", role_id)
