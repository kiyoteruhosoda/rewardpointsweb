"""Authentication API (login, token refresh, profile, password change / reset).

The login identifier is ``username`` (ADR-0011). Email addresses are optional, so accounts
without one (children) can still log in and change their password. Only the SMTP-based reset
needs an email address; accounts without one recover via a temporary password issued by a
parent (``/api/families/...``).
"""

from __future__ import annotations

import logging
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Response, status
from sqlalchemy import select
from sqlalchemy.orm import Session
from werkzeug.security import check_password_hash, generate_password_hash

from bounded_contexts.account_security.application.use_cases.throttle_login import ThrottleLogin
from bounded_contexts.account_security.application.use_cases.verify_second_factor import (
    VerifySecondFactor,
)
from bounded_contexts.account_security.domain.entities.login_attempts import (
    PURPOSE_LOGIN,
    PURPOSE_PASSWORD_RESET,
)
from bounded_contexts.account_security.domain.exceptions import (
    InvalidTotpCodeError,
    TotpRequiredError,
)
from bounded_contexts.account_security.presentation import dependencies as security
from presentation.fastapi.dependencies.auth import (
    clear_access_token_cookie,
    get_current_principal,
    get_person_principal,
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
# Use only for paths allowed even while logged in with a temporary password (who-am-I, logout, change)
PrincipalDep = Annotated[AuthenticatedPrincipal, Depends(get_current_principal)]
# Profile-changing paths. Display devices are not allowed (ADR-0047)
PersonPrincipalDep = Annotated[AuthenticatedPrincipal, Depends(get_person_principal)]
SecondFactorDep = Annotated[VerifySecondFactor, Depends(security.verify_second_factor)]
# Failure counting per login identifier (ADR-0055)
ThrottleDep = Annotated[ThrottleLogin, Depends(security.throttle_login)]

#: Hash used to equalise verification time for unknown identifiers and users without a password.
#: **Matches nothing** (prevents revealing existence through response time; ADR-0055)
_DUMMY_HASH = generate_password_hash("no-account-has-this-password")


def _find_by_username(db: Session, raw: str) -> User | None:
    try:
        username = Username(raw).value
    except ValueError:
        # Not a valid identifier. Treat it the same as a non-existent account
        return None
    return db.scalar(select(User).where(User.username == username))


def _rejection_reason(user: User, password: str) -> str | None:
    """Rejection reason code. ``None`` means accept.

    An expired temporary password is refused even when entered correctly (ADR-0011). But folding
    it into ``invalid_credentials`` would look to the person like "what should be right is not
    accepted", and they would not know to ask a parent to reissue it. Only **the person who knows
    the correct temporary password** can reach this branch, so returning the reason does not tell
    the account's state to anyone who does not know it.
    """
    if user.password_hash is None:
        # A user without a password as a way in (ADR-0034). There is nothing to verify against,
        # so refuse here. Do not use a distinct reason. Keep the verification time equal
        check_password_hash(_DUMMY_HASH, password)
        return "invalid_credentials"
    if not check_password_hash(user.password_hash, password):
        return "invalid_credentials"
    expires_at = user.temporary_password_expires_at
    if user.must_change_password and expires_at is not None and expires_at < utcnow():
        return "temporary_password_expired"
    return None


def _token_response(pair: dict[str, object], user: User) -> TokenResponse:
    return TokenResponse(
        access_token=str(pair["access_token"]),
        refresh_token=_refresh_token_of(pair),
        token_type=str(pair["token_type"]),
        expires_in=int(str(pair["expires_in"])),
        must_change_password=user.must_change_password,
    )


def _refresh_token_of(pair: dict[str, object]) -> str | None:
    """Absent for logins via SSO (ADR-0058)."""
    value = pair["refresh_token"]
    return value if isinstance(value, str) else None


@router.post("/login", response_model=TokenResponse)
def login(
    *,
    body: LoginRequest,
    response: Response,
    db: DbDep,
    second_factor: SecondFactorDep,
    throttle: ThrottleDep,
) -> TokenResponse:
    """Password authentication. With 2FA enabled, ``totp_code`` is also required.

    A missing code returns ``totp_required`` and a mismatch returns ``invalid_totp``. Both mean the
    password was correct, but no token has been issued yet at this point, so the client just
    logs in again with the code.

    Failures (including wrong 2FA codes) are counted per identifier; once the limit is reached,
    requests are refused with 429 ``too_many_attempts`` for a while, even with the correct password (ADR-0055).
    """
    throttle.require_allowed(PURPOSE_LOGIN, body.username, utcnow())

    def _reject(reason: str) -> HTTPException:
        # Log failed logins at WARNING (401 is INFO by default). Whether attempts keep coming is
        # something operations wants to see, so do not bury it. The user name is not written
        # (the logging section of CLAUDE.md) — trace via requestId.
        logger.warning("login_failed: %s", reason)
        if throttle.record_attempt(PURPOSE_LOGIN, body.username, utcnow()):
            # This attempt started the lockout. Operations wants to see that someone is trying
            logger.warning("login_locked")
        return HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={"error": reason},
        )

    user = _find_by_username(db, body.username)
    if user is None or not user.is_active:
        # Equalise verification time for unknown identifiers too, so response time does not reveal existence
        check_password_hash(_DUMMY_HASH, body.password)
        raise _reject("invalid_credentials")
    rejection = _rejection_reason(user, body.password)
    if rejection is not None:
        raise _reject(rejection)

    try:
        second_factor.execute(user_id=user.id, code=body.totp_code)
    except (TotpRequiredError, InvalidTotpCodeError) as error:
        # Normalise to 401 as an authentication failure (the default mapping gives 400).
        # Wrong codes count the same as wrong passwords (no brute-forcing the 6 digits)
        raise _reject(error.code) from None

    # Signed in correctly. Earlier failures were typos, so forget them
    throttle.record_success(PURPOSE_LOGIN, body.username)
    pair = TokenService.create_token_pair(user)
    set_access_token_cookie(response, str(pair["access_token"]))
    logger.info("login_succeeded")
    return _token_response(pair, user)


@router.post("/refresh", response_model=TokenResponse)
def refresh(body: RefreshRequest, response: Response, db: DbDep) -> TokenResponse:
    refreshed = TokenService.verify_refresh_token(body.refresh_token, session=db)
    # Refresh tokens of logins via SSO are not accepted (ADR-0058), even ones issued before this mechanism
    # and still held by the UI — the aim is to block continued use from a stolen token. On 401 the UI asks the IdP again
    if refreshed is None or refreshed.federated_login is not None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={"error": "invalid_token"},
        )
    user = refreshed.user
    pair = TokenService.create_token_pair(user, federated_login=refreshed.federated_login)
    set_access_token_cookie(response, str(pair["access_token"]))
    return _token_response(pair, user)


@router.post("/logout", response_model=StatusResponse)
async def logout(response: Response) -> StatusResponse:
    clear_access_token_cookie(response)
    return StatusResponse(status="ok")


@router.get("/me", response_model=MeResponse)
def me(principal: PrincipalDep, db: DbDep) -> MeResponse:
    """Who am I.

    ⚠ **Name and email are read from the row** (ADR-0037). Token claims are a copy taken at
    issuance and would return stale values right after an edit — **this path has the row**,
    so use it.
    """
    user = db.get(User, principal.user_id)
    return MeResponse(
        user_id=principal.user_id,
        username=user.username if user is not None else principal.username,
        display_name=user.display_name if user is not None else principal.display_name,
        email=user.email if user is not None else principal.email,
        scopes=sorted(principal.permissions),
        must_change_password=user.must_change_password if user is not None else principal.must_change_password,
        # The row is missing only when racing with a deletion. In that case lean towards "has one"
        # (it only changes what the UI shows; what is refused stays refused).
        has_password=user.has_local_password if user is not None else True,
        display_device=principal.via_display_device,
    )


def _resolved_email(db: Session, email: str | None, *, user_id: int) -> str | None:
    """Check that no other account uses it (``null`` clears it)."""
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
def update_profile(body: ProfileUpdateRequest, principal: PersonPrincipalDep, db: DbDep) -> MeResponse:
    """Change one's own display name and email address.

    The login identifier (``username``) is not changed here. Changing it would change how one
    logs in and no longer match the ID the family gave the person.

    Refused while logged in with a temporary password: swapping the email address would let
    someone steal the reset destination before the owner takes it back (ADR-0011). Display devices
    are refused too (ADR-0047; being able to add an email would create a way in that survives removal).
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
        has_password=user.has_local_password,
    )


@router.post("/change-password", response_model=TokenResponse)
def change_password(
    *, body: ChangePasswordRequest, principal: PrincipalDep, db: DbDep, response: Response
) -> TokenResponse:
    """Change the password. **Issue new tokens when done.**

    When logged in with a temporary password, only this path is open, and the gate on other
    operations is lifted once the change is done (ADR-0011).

    ⚠ **The gate is not lifted unless tokens are reissued** (ADR-0037). The temporary-password flag
    is baked into the access token, so merely updating the row leaves the held token still saying
    "not changed yet".
    """
    user = db.get(User, principal.user_id)
    if user is None or user.password_hash is None or not check_password_hash(user.password_hash, body.current_password):
        # ⚠ **Users without a password are also refused here** (ADR-0034). No distinct reason
        # — revealing "has none" would let outsiders count which ways in exist.
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"error": "invalid_current_password"},
        )
    user.password_hash = generate_password_hash(body.new_password)
    user.must_change_password = False
    user.temporary_password_expires_at = None
    db.flush()
    logger.info("password_changed")
    pair = TokenService.create_token_pair(user)
    set_access_token_cookie(response, str(pair["access_token"]))
    return _token_response(pair, user)


@router.post("/forgot-password", response_model=StatusResponse)
def forgot_password(body: ForgotPasswordRequest, db: DbDep, throttle: ThrottleDep) -> StatusResponse:
    """Request a reset link.

    Accounts without an email address (children) cannot be sent a link. The response is still
    the same as for a non-existent user name (so outsiders cannot check whether a child's user
    name exists; task #733). The UI always points to a temporary password from a parent (ADR-0011).

    When mail is disabled or SMTP is unreachable, ``mail_unavailable`` is returned. Returning
    ``accepted`` when nothing can be sent would leave people waiting for mail that never arrives.
    While SMTP is unreachable, non-existent names also get ``mail_unavailable`` (task #768).
    """
    # Count per identifier. **Successes count too** — a success still sends mail to the person,
    # so without counting, knowing the identifier alone would be enough to flood their inbox (ADR-0055)
    throttle.require_allowed(PURPOSE_PASSWORD_RESET, body.username, utcnow())
    throttle.record_attempt(PURPOSE_PASSWORD_RESET, body.username, utcnow())
    outcome = PasswordResetService().request_reset(db, body.username)
    return StatusResponse(status=outcome.value)


@router.post("/reset-password", response_model=StatusResponse)
def reset_password(body: ResetPasswordRequest, db: DbDep) -> StatusResponse:
    if not PasswordResetService().reset(db, body.token, body.new_password):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"error": "invalid_or_expired_token"},
        )
    return StatusResponse(status="ok")
