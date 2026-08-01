"""ドメイン例外 → HTTP 応答の対応付け。

ルーターに ``try/except`` を散らさないよう、アプリ全体の例外ハンドラとして一度
だけ登録する。応答本文はエラーコードのみで、表示文言はフロントエンドが決める
（CLAUDE.md「国際化」）。
"""

from __future__ import annotations

from fastapi import FastAPI, Request, status
from fastapi.responses import JSONResponse

from bounded_contexts.reward_points.domain.exceptions import (
    AccountAlreadyInFamilyError,
    ChildAccountRequiredError,
    DisplayNameRequiredError,
    FamilyAccessDeniedError,
    FamilyNotFoundError,
    InvitationNotFoundError,
    InvitationTargetUnavailableError,
    LedgerNotEmptyError,
    LedgerNotFoundError,
    MembershipNotFoundError,
    MembershipNotLinkedError,
    ReversalOfReversalError,
    RewardPointsError,
    TransactionAlreadyReversedError,
    TransactionNotFoundError,
    UsernameAlreadyTakenError,
)

_STATUS_BY_ERROR: dict[type[RewardPointsError], int] = {
    FamilyNotFoundError: status.HTTP_404_NOT_FOUND,
    FamilyAccessDeniedError: status.HTTP_403_FORBIDDEN,
    MembershipNotFoundError: status.HTTP_404_NOT_FOUND,
    LedgerNotFoundError: status.HTTP_404_NOT_FOUND,
    TransactionNotFoundError: status.HTTP_404_NOT_FOUND,
    InvitationNotFoundError: status.HTTP_404_NOT_FOUND,
    TransactionAlreadyReversedError: status.HTTP_409_CONFLICT,
    AccountAlreadyInFamilyError: status.HTTP_409_CONFLICT,
    InvitationTargetUnavailableError: status.HTTP_409_CONFLICT,
    UsernameAlreadyTakenError: status.HTTP_409_CONFLICT,
    LedgerNotEmptyError: status.HTTP_409_CONFLICT,
    ReversalOfReversalError: status.HTTP_400_BAD_REQUEST,
    ChildAccountRequiredError: status.HTTP_403_FORBIDDEN,
    MembershipNotLinkedError: status.HTTP_400_BAD_REQUEST,
    DisplayNameRequiredError: status.HTTP_400_BAD_REQUEST,
}


def status_for(error: RewardPointsError) -> int:
    return _STATUS_BY_ERROR.get(type(error), status.HTTP_400_BAD_REQUEST)


def register_reward_points_error_handler(app: FastAPI) -> None:
    @app.exception_handler(RewardPointsError)
    async def _handle(_: Request, error: RewardPointsError) -> JSONResponse:
        return JSONResponse(status_code=status_for(error), content={"detail": {"error": error.code}})


__all__ = ["register_reward_points_error_handler", "status_for"]
