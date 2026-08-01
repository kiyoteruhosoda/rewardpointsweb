"""ユーザー管理 API（要 ``user:manage``）。

アカウントの追加・変更・削除はアプリログへ残す。他人のアカウントに手を入れる
操作で、後から「いつ誰のアカウントが変わったか」を追えないと困るため。
**識別子は本文に入れる**——``log`` テーブルへ入るのは列にある項目だけで、
``extra`` の残りは stdout の JSON にしか出ない。ユーザー名・メールアドレスは
書かない（CLAUDE.md「ログ」）。
"""

from __future__ import annotations

import logging
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session
from werkzeug.security import generate_password_hash

from bounded_contexts.reward_points.application.use_cases.ensure_user_can_be_deleted import (
    EnsureUserCanBeDeletedUseCase,
)
from bounded_contexts.reward_points.domain.exceptions import UserStillOwnsFamiliesError
from bounded_contexts.reward_points.presentation.dependencies import (
    get_ensure_user_can_be_deleted_use_case,
)
from presentation.fastapi.dependencies.auth import require_permission
from presentation.fastapi.schemas.admin import (
    UserCreateRequest,
    UserResponse,
    UserUpdateRequest,
)
from shared.domain.auth.username import Username
from shared.infrastructure.models import Role, User
from shared.kernel.database.session import get_db

logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/api/admin/users",
    tags=["admin"],
    dependencies=[Depends(require_permission("user:manage"))],
)

DbDep = Annotated[Session, Depends(get_db)]
DeletableDep = Annotated[EnsureUserCanBeDeletedUseCase, Depends(get_ensure_user_can_be_deleted_use_case)]


def _to_response(user: User) -> UserResponse:
    return UserResponse(
        id=user.id,
        username=user.username,
        email=user.email,
        display_name=user.display_name,
        is_active=user.is_active,
        must_change_password=user.must_change_password,
        roles=sorted(r.name for r in user.roles),
    )


def _changed_fields(body: UserUpdateRequest) -> list[str]:
    """変更した項目の名前だけを並べる（値は残さない）。"""
    candidates = (
        ("display_name", body.display_name),
        ("is_active", body.is_active),
        ("roles", body.roles),
        ("password", body.password),
    )
    return [name for name, value in candidates if value is not None]


def _resolve_roles(db: Session, names: list[str]) -> list[Role]:
    roles = db.scalars(select(Role).where(Role.name.in_(names))).all()
    missing = set(names) - {r.name for r in roles}
    if missing:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"error": "unknown_roles", "roles": sorted(missing)},
        )
    return list(roles)


@router.get("", response_model=list[UserResponse])
async def list_users(db: DbDep) -> list[UserResponse]:
    users = db.scalars(select(User).order_by(User.id)).all()
    return [_to_response(u) for u in users]


@router.post("", status_code=status.HTTP_201_CREATED, response_model=UserResponse)
async def create_user(body: UserCreateRequest, db: DbDep) -> UserResponse:
    try:
        username = Username(body.username).value
    except ValueError as error:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"error": "invalid_username"},
        ) from error
    if db.scalar(select(User).where(User.username == username)):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={"error": "username_already_taken"},
        )
    if body.email and db.scalar(select(User).where(User.email == body.email)):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={"error": "email_already_exists"},
        )
    user = User(
        username=username,
        email=body.email,
        display_name=body.display_name,
        password_hash=generate_password_hash(body.password),
        is_active=True,
    )
    user.roles = _resolve_roles(db, body.roles)
    db.add(user)
    db.flush()
    logger.info("admin_user_created: user_id=%s", user.id)
    return _to_response(user)


@router.put("/{user_id}", response_model=UserResponse)
async def update_user(user_id: int, body: UserUpdateRequest, db: DbDep) -> UserResponse:
    user = db.get(User, user_id)
    if user is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail={"error": "user_not_found"})
    if body.display_name is not None:
        user.display_name = body.display_name
    if body.is_active is not None:
        user.is_active = body.is_active
    if body.roles is not None:
        user.roles = _resolve_roles(db, body.roles)
    if body.password is not None:
        user.password_hash = generate_password_hash(body.password)
    db.flush()
    logger.info("admin_user_updated: user_id=%s fields=%s", user_id, ",".join(_changed_fields(body)) or "none")
    return _to_response(user)


@router.delete("/{user_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_user(user_id: int, db: DbDep, deletable: DeletableDep) -> None:
    """アカウントを削除する。

    家族の owner として残っているアカウントは削除できない（409）。無効化したい
    だけなら `is_active` を偽にする。家族への参加と台帳の操作者は、アカウントが
    消えても外部キーの `ON DELETE` が追随する（ADR-0009）。
    """
    user = db.get(User, user_id)
    if user is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail={"error": "user_not_found"})
    try:
        deletable.execute(user_id=user_id)
    except UserStillOwnsFamiliesError as error:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail={"error": error.code}) from error
    user.roles = []
    db.delete(user)
    logger.info("admin_user_deleted: user_id=%s", user_id)
