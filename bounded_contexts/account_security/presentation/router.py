"""Account security API (the logged-in user manages their own settings).

Only "oneself" is in scope. Other people's accounts are not handled, so no scope is required;
being authenticated is the only condition (admin operations touching someone else's two-factor authentication
are the responsibility of ``/api/admin/users``).
"""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, status

from bounded_contexts.account_security.application.dto.account_security_dto import (
    PasskeySummaryDto,
)
from bounded_contexts.account_security.application.use_cases.manage_passkeys import (
    DeletePasskey,
    ListPasskeys,
)
from bounded_contexts.account_security.application.use_cases.manage_totp import (
    ConfirmTotpEnrollment,
    DisableTotp,
    GetTwoFactorStatus,
    StartTotpEnrollment,
)
from bounded_contexts.account_security.application.use_cases.register_passkey import (
    CompletePasskeyRegistration,
    StartPasskeyRegistration,
)
from bounded_contexts.account_security.presentation import dependencies
from bounded_contexts.account_security.presentation.qr_code import (
    render_qr_code_data_uri,
)
from bounded_contexts.account_security.presentation.schemas import (
    PasskeyChallengeResponse,
    PasskeyRegistrationRequest,
    PasskeyResponse,
    TotpCodeRequest,
    TotpEnrollmentResponse,
    TwoFactorStatusResponse,
)
from presentation.fastapi.dependencies.auth import get_settled_principal
from presentation.fastapi.schemas.auth import StatusResponse
from shared.application.authenticated_principal import AuthenticatedPrincipal
from shared.kernel.timestamps import isoformat_utc

router = APIRouter(prefix="/api/account/security", tags=["account-security"])

# Not allowed while logged in with a temporary password, so that the second factor cannot be
# replaced before the actual user does it (ADR-0011).
#: ⚠ **Gate for routes that change credentials** (ADR-0037). Only here is the row re-read -- the temporary
#: password flag is a value baked into the token, so it would be pointless if two-factor or passkeys could be
#: replaced right after it was set (ADR-0011).
PrincipalDep = Annotated[AuthenticatedPrincipal, Depends(get_settled_principal)]


def _to_passkey_response(summary: PasskeySummaryDto) -> PasskeyResponse:
    return PasskeyResponse(
        id=summary.id,
        name=summary.name,
        transports=list(summary.transports),
        created_at=isoformat_utc(summary.created_at) if summary.created_at else None,
        last_used_at=isoformat_utc(summary.last_used_at) if summary.last_used_at else None,
    )


# ---------------------------------------------------------------------------
# Two-factor authentication (TOTP)
# ---------------------------------------------------------------------------


@router.get("/two-factor", response_model=TwoFactorStatusResponse)
def two_factor_status(
    principal: PrincipalDep,
    use_case: Annotated[GetTwoFactorStatus, Depends(dependencies.get_two_factor_status)],
) -> TwoFactorStatusResponse:
    status_dto = use_case.execute(principal.user_id)
    return TwoFactorStatusResponse(enabled=status_dto.enabled, enrolling=status_dto.enrolling)


@router.post("/two-factor/enrollment", response_model=TotpEnrollmentResponse)
def start_two_factor_enrollment(
    principal: PrincipalDep,
    use_case: Annotated[StartTotpEnrollment, Depends(dependencies.start_totp_enrollment)],
) -> TotpEnrollmentResponse:
    """Issue a shared key. Two-factor authentication is not enabled yet at this point."""
    enrollment = use_case.execute(user_id=principal.user_id, account_name=principal.username)
    return TotpEnrollmentResponse(
        secret=enrollment.secret,
        otpauth_uri=enrollment.otpauth_uri,
        qr_code=render_qr_code_data_uri(enrollment.otpauth_uri),
    )


@router.post("/two-factor/confirmation", response_model=StatusResponse)
def confirm_two_factor_enrollment(
    body: TotpCodeRequest,
    principal: PrincipalDep,
    use_case: Annotated[ConfirmTotpEnrollment, Depends(dependencies.confirm_totp_enrollment)],
) -> StatusResponse:
    """Verify the authenticator app's code and enable two-factor authentication."""
    use_case.execute(user_id=principal.user_id, code=body.code)
    return StatusResponse(status="ok")


@router.post("/two-factor/removal", response_model=StatusResponse)
def disable_two_factor(
    body: TotpCodeRequest,
    principal: PrincipalDep,
    use_case: Annotated[DisableTotp, Depends(dependencies.disable_totp)],
) -> StatusResponse:
    use_case.execute(user_id=principal.user_id, code=body.code)
    return StatusResponse(status="ok")


# ---------------------------------------------------------------------------
# Passkeys (WebAuthn)
# ---------------------------------------------------------------------------


@router.get("/passkeys", response_model=list[PasskeyResponse])
def list_registered_passkeys(
    principal: PrincipalDep,
    use_case: Annotated[ListPasskeys, Depends(dependencies.list_passkeys)],
) -> list[PasskeyResponse]:
    return [_to_passkey_response(item) for item in use_case.execute(principal.user_id)]


@router.post("/passkeys/registration", response_model=PasskeyChallengeResponse)
def start_passkey_registration(
    principal: PrincipalDep,
    use_case: Annotated[StartPasskeyRegistration, Depends(dependencies.start_passkey_registration)],
) -> PasskeyChallengeResponse:
    """Issue a registration challenge (for ``navigator.credentials.create``)."""
    challenge = use_case.execute(
        user_id=principal.user_id,
        user_name=principal.username,
        display_name=principal.display_name,
    )
    return PasskeyChallengeResponse(challenge_id=challenge.challenge_id, public_key=challenge.public_key)


@router.post(
    "/passkeys",
    response_model=PasskeyResponse,
    status_code=status.HTTP_201_CREATED,
)
def complete_passkey_registration(
    body: PasskeyRegistrationRequest,
    principal: PrincipalDep,
    use_case: Annotated[CompletePasskeyRegistration, Depends(dependencies.complete_passkey_registration)],
) -> PasskeyResponse:
    summary = use_case.execute(
        user_id=principal.user_id,
        challenge_id=body.challenge_id,
        credential=body.credential,
        name=body.name,
    )
    return _to_passkey_response(summary)


@router.delete("/passkeys/{passkey_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_registered_passkey(
    passkey_id: int,
    principal: PrincipalDep,
    use_case: Annotated[DeletePasskey, Depends(dependencies.delete_passkey)],
) -> None:
    use_case.execute(user_id=principal.user_id, passkey_id=passkey_id)
