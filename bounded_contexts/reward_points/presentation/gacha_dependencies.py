"""Assembly of the gacha use cases for ``Depends()`` (ADR-0060)."""

from __future__ import annotations

from typing import Annotated

from fastapi import Depends

from bounded_contexts.reward_points.application.use_cases.draw_gacha import (
    DrawGachaUseCase,
    HandOverGachaPrizeUseCase,
    TryGachaUseCase,
)
from bounded_contexts.reward_points.application.use_cases.manage_gachas import (
    DeleteGachaUseCase,
    GachaRepositories,
    SaveGachaUseCase,
    ViewGachaBoardUseCase,
)
from bounded_contexts.reward_points.infrastructure.sql_gacha_repository import (
    SqlGachaDrawRepository,
    SqlGachaRepository,
)
from bounded_contexts.reward_points.presentation.dependencies import (
    AccessDep,
    DbDep,
    MembershipRepoDep,
    TransactionRepoDep,
)


def get_gacha_repository(db: DbDep) -> SqlGachaRepository:
    return SqlGachaRepository(db)


def get_gacha_draw_repository(db: DbDep) -> SqlGachaDrawRepository:
    return SqlGachaDrawRepository(db)


GachaRepoDep = Annotated[SqlGachaRepository, Depends(get_gacha_repository)]
GachaDrawRepoDep = Annotated[SqlGachaDrawRepository, Depends(get_gacha_draw_repository)]


def get_view_gacha_board_use_case(
    *,
    access: AccessDep,
    gachas: GachaRepoDep,
    draws: GachaDrawRepoDep,
    transactions: TransactionRepoDep,
    memberships: MembershipRepoDep,
) -> ViewGachaBoardUseCase:
    stores = GachaRepositories(gachas=gachas, draws=draws, transactions=transactions, memberships=memberships)
    return ViewGachaBoardUseCase(access, stores)


def get_save_gacha_use_case(access: AccessDep, gachas: GachaRepoDep) -> SaveGachaUseCase:
    return SaveGachaUseCase(access, gachas)


def get_delete_gacha_use_case(access: AccessDep, gachas: GachaRepoDep) -> DeleteGachaUseCase:
    return DeleteGachaUseCase(access, gachas)


def get_draw_gacha_use_case(
    *, access: AccessDep, gachas: GachaRepoDep, draws: GachaDrawRepoDep, transactions: TransactionRepoDep
) -> DrawGachaUseCase:
    return DrawGachaUseCase(access=access, gachas=gachas, draws=draws, transactions=transactions)


def get_try_gacha_use_case(access: AccessDep, gachas: GachaRepoDep) -> TryGachaUseCase:
    return TryGachaUseCase(access, gachas)


def get_hand_over_gacha_prize_use_case(access: AccessDep, draws: GachaDrawRepoDep) -> HandOverGachaPrizeUseCase:
    return HandOverGachaPrizeUseCase(access, draws)


ViewGachaBoardDep = Annotated[ViewGachaBoardUseCase, Depends(get_view_gacha_board_use_case)]
SaveGachaDep = Annotated[SaveGachaUseCase, Depends(get_save_gacha_use_case)]
DeleteGachaDep = Annotated[DeleteGachaUseCase, Depends(get_delete_gacha_use_case)]
DrawGachaDep = Annotated[DrawGachaUseCase, Depends(get_draw_gacha_use_case)]
TryGachaDep = Annotated[TryGachaUseCase, Depends(get_try_gacha_use_case)]
HandOverGachaPrizeDep = Annotated[HandOverGachaPrizeUseCase, Depends(get_hand_over_gacha_prize_use_case)]


__all__ = [
    "DeleteGachaDep",
    "DrawGachaDep",
    "GachaDrawRepoDep",
    "GachaRepoDep",
    "HandOverGachaPrizeDep",
    "SaveGachaDep",
    "TryGachaDep",
    "ViewGachaBoardDep",
    "get_draw_gacha_use_case",
    "get_try_gacha_use_case",
]
