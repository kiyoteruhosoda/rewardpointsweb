"""ドメイン例外 → HTTP 応答の対応付け。

ルーターに ``try/except`` を散らさないよう、アプリ全体の例外ハンドラとして一度
だけ登録する。応答本文はエラーコードのみで、表示文言はフロントエンドが決める
（CLAUDE.md「国際化」）。
"""

from __future__ import annotations

from fastapi import FastAPI, Request, status
from fastapi.responses import JSONResponse

from bounded_contexts.reward_points.domain.exceptions import (
    LinkedUserAlreadyTakenError,
    MemberAccessDeniedError,
    MemberAlreadySharedError,
    MemberNotFoundError,
    MemberShareNotFoundError,
    PointEntryNotFoundError,
    RewardPointsError,
    ShareTargetNotFoundError,
    ShareWithOwnerNotAllowedError,
)

_STATUS_BY_ERROR: dict[type[RewardPointsError], int] = {
    MemberNotFoundError: status.HTTP_404_NOT_FOUND,
    MemberAccessDeniedError: status.HTTP_403_FORBIDDEN,
    PointEntryNotFoundError: status.HTTP_404_NOT_FOUND,
    MemberShareNotFoundError: status.HTTP_404_NOT_FOUND,
    ShareTargetNotFoundError: status.HTTP_404_NOT_FOUND,
    MemberAlreadySharedError: status.HTTP_409_CONFLICT,
    LinkedUserAlreadyTakenError: status.HTTP_409_CONFLICT,
    ShareWithOwnerNotAllowedError: status.HTTP_400_BAD_REQUEST,
}


def status_for(error: RewardPointsError) -> int:
    return _STATUS_BY_ERROR.get(type(error), status.HTTP_400_BAD_REQUEST)


def register_reward_points_error_handler(app: FastAPI) -> None:
    @app.exception_handler(RewardPointsError)
    async def _handle(_: Request, error: RewardPointsError) -> JSONResponse:
        return JSONResponse(status_code=status_for(error), content={"detail": {"error": error.code}})


__all__ = ["register_reward_points_error_handler", "status_for"]
