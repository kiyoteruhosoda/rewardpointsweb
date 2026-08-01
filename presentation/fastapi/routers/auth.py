"""認証 API（ログイン・トークン更新・プロフィール・パスワード変更／リセット）。

ログインの識別子は ``username``（ADR-0011）。メールアドレスは任意項目のため、
持たないアカウント（子ども）でもログイン・パスワード変更ができる。SMTP を使う
リセットだけがメールアドレスを必要とし、持たないアカウントの回復は親からの
一時パスワード発行（``/api/families/...``）で行う。
"""

from __future__ import annotations

import logging
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Response, status
from sqlalchemy import select
from sqlalchemy.orm import Session
from werkzeug.security import check_password_hash, generate_password_hash

from bounded_contexts.account_security.application.use_cases.verify_second_factor import (
    VerifySecondFactor,
)
from bounded_contexts.account_security.domain.exceptions import (
    InvalidTotpCodeError,
    TotpRequiredError,
)
from bounded_contexts.account_security.presentation import dependencies as security
from presentation.fastapi.dependencies.auth import (
    clear_access_token_cookie,
    get_current_principal,
    set_access_token_cookie,
)
from presentation.fastapi.schemas.auth import (
    ChangePasswordRequest,
    ForgotPasswordRequest,
    LoginRequest,
    MeResponse,
    ProfileUpdateRequest,
    RefreshRequest,
    ResetPasswordRequest,
    StatusResponse,
    TokenResponse,
)
from presentation.fastapi.services.password_reset_service import PasswordResetService
from presentation.fastapi.services.token_service import TokenService
from shared.application.authenticated_principal import AuthenticatedPrincipal
from shared.domain.auth.username import Username
from shared.infrastructure.models import User
from shared.kernel.database.session import get_db
from shared.kernel.timestamps import utcnow

router = APIRouter(prefix="/api/auth", tags=["auth"])
logger = logging.getLogger(__name__)

DbDep = Annotated[Session, Depends(get_db)]
PrincipalDep = Annotated[AuthenticatedPrincipal, Depends(get_current_principal)]
SecondFactorDep = Annotated[VerifySecondFactor, Depends(security.verify_second_factor)]


def _find_by_username(db: Session, raw: str) -> User | None:
    try:
        username = Username(raw).value
    except ValueError:
        # 識別子として成立しない文字列。存在しないアカウントと同じ扱いにする
        return None
    return db.scalar(select(User).where(User.username == username))


def _password_accepted(user: User, password: str) -> bool:
    if not check_password_hash(user.password_hash, password):
        return False
    expires_at = user.temporary_password_expires_at
    # 期限切れの一時パスワードは、正しく入力されても通さない（ADR-0011）
    return not (user.must_change_password and expires_at is not None and expires_at < utcnow())


def _token_response(pair: dict[str, object], user: User) -> TokenResponse:
    return TokenResponse(
        access_token=str(pair["access_token"]),
        refresh_token=str(pair["refresh_token"]),
        token_type=str(pair["token_type"]),
        expires_in=int(str(pair["expires_in"])),
        must_change_password=user.must_change_password,
    )


@router.post("/login", response_model=TokenResponse)
async def login(
    body: LoginRequest,
    response: Response,
    db: DbDep,
    second_factor: SecondFactorDep,
) -> TokenResponse:
    """パスワード認証。二要素認証が有効なら ``totp_code`` も必須になる。

    コード未提示は ``totp_required``、不一致は ``invalid_totp`` を返す。どちらも
    パスワードは正しかったことを意味するが、この時点ではまだトークンを発行して
    いないため、コードを添えて再度ログインすればよい。
    """
    user = _find_by_username(db, body.username)
    if user is None or not user.is_active or not _password_accepted(user, body.password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={"error": "invalid_credentials"},
        )

    try:
        second_factor.execute(user_id=user.id, code=body.totp_code)
    except (TotpRequiredError, InvalidTotpCodeError) as error:
        # 認証の失敗として 401 に揃える（既定の対応付けでは 400 になる）
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={"error": error.code},
        ) from None

    pair = TokenService.create_token_pair(user)
    set_access_token_cookie(response, str(pair["access_token"]))
    logger.info("login_succeeded")
    return _token_response(pair, user)


@router.post("/refresh", response_model=TokenResponse)
async def refresh(body: RefreshRequest, response: Response, db: DbDep) -> TokenResponse:
    user = TokenService.verify_refresh_token(body.refresh_token, session=db)
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={"error": "invalid_token"},
        )
    pair = TokenService.create_token_pair(user)
    set_access_token_cookie(response, str(pair["access_token"]))
    return _token_response(pair, user)


@router.post("/logout", response_model=StatusResponse)
async def logout(response: Response) -> StatusResponse:
    clear_access_token_cookie(response)
    return StatusResponse(status="ok")


@router.get("/me", response_model=MeResponse)
async def me(principal: PrincipalDep) -> MeResponse:
    return MeResponse(
        user_id=principal.user_id,
        username=principal.username,
        display_name=principal.display_name,
        email=principal.email,
        scopes=sorted(principal.permissions),
        must_change_password=principal.must_change_password,
    )


def _resolved_email(db: Session, email: str | None, *, user_id: int) -> str | None:
    """他のアカウントが使っていないことを確かめる（``null`` は解除）。"""
    if email is None:
        return None
    normalized = email.strip().lower()
    taken = db.scalar(select(User.id).where(User.email == normalized, User.id != user_id))
    if taken is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={"error": "email_already_exists"},
        )
    return normalized


@router.put("/me", response_model=MeResponse)
async def update_profile(body: ProfileUpdateRequest, principal: PrincipalDep, db: DbDep) -> MeResponse:
    """自分の表示名とメールアドレスを変える。

    ログイン識別子（``username``）はここでは変えない。変えるとログインの手順が
    変わり、家族から本人へ伝えた ID とも食い違う。
    """
    user = db.get(User, principal.user_id)
    if user is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail={"error": "user_not_found"})
    if body.display_name is not None:
        user.display_name = body.display_name
    if "email" in body.model_fields_set:
        user.email = _resolved_email(db, body.email, user_id=user.id)
    db.flush()
    logger.info("profile_updated")
    return MeResponse(
        user_id=user.id,
        username=user.username,
        display_name=user.display_name,
        email=user.email,
        scopes=sorted(principal.permissions),
        must_change_password=user.must_change_password,
    )


@router.post("/change-password", response_model=StatusResponse)
async def change_password(body: ChangePasswordRequest, principal: PrincipalDep, db: DbDep) -> StatusResponse:
    """パスワードを変える。

    一時パスワードでログインしている場合はこの経路だけが開いており、変更を
    終えた時点で他の操作の関門が外れる（ADR-0011）。
    """
    user = db.get(User, principal.user_id)
    if user is None or not check_password_hash(user.password_hash, body.current_password):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"error": "invalid_current_password"},
        )
    user.password_hash = generate_password_hash(body.new_password)
    user.must_change_password = False
    user.temporary_password_expires_at = None
    logger.info("password_changed")
    return StatusResponse(status="ok")


@router.post("/forgot-password", response_model=StatusResponse)
async def forgot_password(body: ForgotPasswordRequest, db: DbDep) -> StatusResponse:
    # ユーザーの存在有無に関わらず同じ応答を返す（列挙攻撃対策）
    PasswordResetService().request_reset(db, body.email)
    return StatusResponse(status="accepted")


@router.post("/reset-password", response_model=StatusResponse)
async def reset_password(body: ResetPasswordRequest, db: DbDep) -> StatusResponse:
    if not PasswordResetService().reset(db, body.token, body.new_password):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"error": "invalid_or_expired_token"},
        )
    return StatusResponse(status="ok")
