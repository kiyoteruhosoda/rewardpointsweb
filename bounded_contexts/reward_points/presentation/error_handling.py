"""Mapping of domain exceptions to HTTP responses.

Registered once as an app-wide exception handler so routers are not littered with
``try/except``. The response body carries only the error code; the display text is decided
by the frontend (CLAUDE.md "i18n").

Recording failures is left to the cross-cutting sink
(:func:`~presentation.fastapi.error_handling.log_failed_request`). Logging separately here
would mix in lines whose level and fields differ from ``HTTPException`` failures, making the
logs hard to filter.
"""

from __future__ import annotations

from fastapi import FastAPI, Request, status
from fastapi.responses import JSONResponse

from bounded_contexts.reward_points.domain.exceptions import (
    AccountAlreadyInFamilyError,
    AlreadyBelongsToFamilyError,
    ChildAccountRequiredError,
    ChildCannotLeaveFamilyError,
    ChildInvitationRequiresSignupError,
    CorrectionOfReversalError,
    DisplayNameRequiredError,
    DisplayNotFoundError,
    FamilyAccessDeniedError,
    FamilyNotEmptyError,
    FamilyNotFoundError,
    GuardianAccountRequiredError,
    GuardianInvitationRequiresSignInError,
    IdempotencyKeyReusedError,
    IndependenceNotProposedError,
    InvalidFamilyArchiveError,
    InvalidMemberOrderError,
    InvitationNotFoundError,
    InvitationTargetUnavailableError,
    LastGuardianCannotLeaveError,
    LedgerNotEmptyError,
    LedgerNotFoundError,
    MembershipNotFoundError,
    MembershipNotLinkedError,
    ReversalOfReversalError,
    RewardEventCompletedError,
    RewardEventDeadlinePassedError,
    RewardEventExpiredError,
    RewardEventNotFoundError,
    RewardPointsError,
    RoleNotInvitableError,
    StickerOutOfOrderError,
    TransactionAlreadyReversedError,
    TransactionNotFoundError,
    UnsupportedArchiveVersionError,
    UsernameAlreadyTakenError,
)
from presentation.fastapi.error_handling import log_failed_request

_STATUS_BY_ERROR: dict[type[RewardPointsError], int] = {
    FamilyNotFoundError: status.HTTP_404_NOT_FOUND,
    FamilyAccessDeniedError: status.HTTP_403_FORBIDDEN,
    MembershipNotFoundError: status.HTTP_404_NOT_FOUND,
    LedgerNotFoundError: status.HTTP_404_NOT_FOUND,
    TransactionNotFoundError: status.HTTP_404_NOT_FOUND,
    InvitationNotFoundError: status.HTTP_404_NOT_FOUND,
    RewardEventNotFoundError: status.HTTP_404_NOT_FOUND,
    DisplayNotFoundError: status.HTTP_404_NOT_FOUND,
    # The screen is looking at a stale state (ADR-0042). Reloading reveals the right number
    RewardEventCompletedError: status.HTTP_409_CONFLICT,
    StickerOutOfOrderError: status.HTTP_409_CONFLICT,
    RewardEventExpiredError: status.HTTP_409_CONFLICT,
    RewardEventDeadlinePassedError: status.HTTP_400_BAD_REQUEST,
    TransactionAlreadyReversedError: status.HTTP_409_CONFLICT,
    AccountAlreadyInFamilyError: status.HTTP_409_CONFLICT,
    AlreadyBelongsToFamilyError: status.HTTP_409_CONFLICT,
    InvitationTargetUnavailableError: status.HTTP_409_CONFLICT,
    UsernameAlreadyTakenError: status.HTTP_409_CONFLICT,
    LedgerNotEmptyError: status.HTTP_409_CONFLICT,
    LastGuardianCannotLeaveError: status.HTTP_409_CONFLICT,
    FamilyNotEmptyError: status.HTTP_409_CONFLICT,
    IndependenceNotProposedError: status.HTTP_409_CONFLICT,
    ReversalOfReversalError: status.HTTP_409_CONFLICT,
    CorrectionOfReversalError: status.HTTP_409_CONFLICT,
    IdempotencyKeyReusedError: status.HTTP_409_CONFLICT,
    ChildAccountRequiredError: status.HTTP_403_FORBIDDEN,
    ChildCannotLeaveFamilyError: status.HTTP_403_FORBIDDEN,
    GuardianAccountRequiredError: status.HTTP_403_FORBIDDEN,
    MembershipNotLinkedError: status.HTTP_400_BAD_REQUEST,
    ChildInvitationRequiresSignupError: status.HTTP_400_BAD_REQUEST,
    GuardianInvitationRequiresSignInError: status.HTTP_400_BAD_REQUEST,
    DisplayNameRequiredError: status.HTTP_400_BAD_REQUEST,
    RoleNotInvitableError: status.HTTP_400_BAD_REQUEST,
    InvalidMemberOrderError: status.HTTP_400_BAD_REQUEST,
    # Archive contents are inconsistent, or its version cannot be read (ADR-0026). Both are
    # problems with what was sent, so 400. The remedies differ, so the codes are separate
    InvalidFamilyArchiveError: status.HTTP_400_BAD_REQUEST,
    UnsupportedArchiveVersionError: status.HTTP_400_BAD_REQUEST,
}


def status_for(error: RewardPointsError) -> int:
    return _STATUS_BY_ERROR.get(type(error), status.HTTP_400_BAD_REQUEST)


def register_reward_points_error_handler(app: FastAPI) -> None:
    @app.exception_handler(RewardPointsError)
    async def _handle(request: Request, error: RewardPointsError) -> JSONResponse:
        status_code = status_for(error)
        log_failed_request(request, status_code, error.code)
        return JSONResponse(status_code=status_code, content={"detail": {"error": error.code}})


__all__ = ["register_reward_points_error_handler", "status_for"]
