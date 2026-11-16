"""API of gacha machines on a child's ledger (ADR-0060).

Same two-stage authorization as the rest of the context: the scope is declared here, and
"may the caller touch this ledger" is decided by
:class:`~bounded_contexts.reward_points.application.family_access_resolver.FamilyAccessResolver`.

- view: ``point:view`` (anyone who can view the ledger)
- create, edit, delete, hand over, trial draw: ``point:manage`` (parents)
- draw, bundle draw: ``gacha:draw`` (parents, and the child on their own ledger)
"""

from __future__ import annotations

import logging
from typing import Annotated

from fastapi import APIRouter, Depends, status

from bounded_contexts.reward_points.application.dto.gacha_dto import GachaDrawDTO, GachaDTO
from bounded_contexts.reward_points.application.use_cases.draw_gacha import DrawGachaCommand, HandOverCommand
from bounded_contexts.reward_points.application.use_cases.manage_gachas import SaveGachaCommand
from bounded_contexts.reward_points.domain.entities.gacha import GachaDesign, GachaPrize
from bounded_contexts.reward_points.presentation.gacha_dependencies import (
    DeleteGachaDep,
    DrawGachaBundleDep,
    DrawGachaDep,
    HandOverGachaPrizeDep,
    SaveGachaDep,
    TryGachaDep,
    ViewGachaBoardDep,
)
from bounded_contexts.reward_points.presentation.gacha_schemas import (
    GachaBoardResponse,
    GachaBundleResultResponse,
    GachaDrawRequest,
    GachaDrawResponse,
    GachaDrawResultResponse,
    GachaPrizeResponse,
    GachaResponse,
    GachaSaveRequest,
    GachaTrialResponse,
)
from presentation.fastapi.dependencies.auth import require_permission
from shared.application.authenticated_principal import AuthenticatedPrincipal

router = APIRouter(prefix="/api/families", tags=["reward-points"])
logger = logging.getLogger(__name__)

PointViewer = Annotated[AuthenticatedPrincipal, Depends(require_permission("point:view"))]
PointManager = Annotated[AuthenticatedPrincipal, Depends(require_permission("point:manage"))]
GachaDrawer = Annotated[AuthenticatedPrincipal, Depends(require_permission("gacha:draw"))]


def _gacha_path(suffix: str = "") -> str:
    return "/{family_id}/ledgers/{ledger_id}/gachas" + suffix


def _draw_path(suffix: str = "") -> str:
    return "/{family_id}/ledgers/{ledger_id}/gacha-draws" + suffix


def _to_gacha(dto: GachaDTO) -> GachaResponse:
    return GachaResponse(
        id=dto.id,
        ledger_id=dto.ledger_id,
        name=dto.name,
        price=dto.price,
        prizes=[GachaPrizeResponse(name=p.name, weight=p.weight, is_miss=p.is_miss) for p in dto.prizes],
        created_at=dto.created_at,
    )


def _to_draw(dto: GachaDrawDTO) -> GachaDrawResponse:
    return GachaDrawResponse(
        id=dto.id,
        gacha_id=dto.gacha_id,
        gacha_name=dto.gacha_name,
        prize_name=dto.prize_name,
        is_miss=dto.is_miss,
        price=dto.price,
        drawn_at=dto.drawn_at,
        handed_over_at=dto.handed_over_at,
        is_bonus=dto.is_bonus,
    )


def _to_design(body: GachaSaveRequest) -> GachaDesign:
    """Turn the request into the domain value. An all-miss machine raises ``GachaNeedsAPrizeError``."""
    return GachaDesign(
        name=body.name,
        price=body.price,
        prizes=tuple(GachaPrize(name=p.name, weight=p.weight, is_miss=p.is_miss) for p in body.prizes),
    )


@router.get(_gacha_path(), response_model=GachaBoardResponse)
def view_gacha_board(ledger_id: int, use_case: ViewGachaBoardDep, principal: PointViewer) -> GachaBoardResponse:
    """Return the child's machines (creation order), recent draws (newest first) and balance."""
    dto = use_case.execute(ledger_id=ledger_id, account_id=principal.user_id)
    return GachaBoardResponse(
        ledger_id=dto.ledger_id,
        display_name=dto.display_name,
        balance=dto.balance,
        can_modify=dto.can_modify,
        can_draw=dto.can_draw,
        gachas=[_to_gacha(gacha) for gacha in dto.gachas],
        draws=[_to_draw(draw) for draw in dto.draws],
    )


@router.post(_gacha_path(), status_code=status.HTTP_201_CREATED, response_model=GachaResponse)
def create_gacha(
    *, ledger_id: int, body: GachaSaveRequest, use_case: SaveGachaDep, principal: PointManager
) -> GachaResponse:
    """Create a machine. At least one prize must not be a miss (400 ``gacha_needs_a_prize``)."""
    dto = use_case.execute(SaveGachaCommand(ledger_id=ledger_id, account_id=principal.user_id, design=_to_design(body)))
    logger.info("gacha_created", extra={"ledger_id": ledger_id, "gacha_id": dto.id})
    return _to_gacha(dto)


@router.put(_gacha_path("/{gacha_id}"), response_model=GachaResponse)
def update_gacha(
    *, ledger_id: int, gacha_id: int, body: GachaSaveRequest, use_case: SaveGachaDep, principal: PointManager
) -> GachaResponse:
    """Replace the name, price and all prizes. Past draws keep what they won."""
    dto = use_case.execute(
        SaveGachaCommand(ledger_id=ledger_id, account_id=principal.user_id, design=_to_design(body), gacha_id=gacha_id)
    )
    logger.info("gacha_updated", extra={"ledger_id": ledger_id, "gacha_id": gacha_id})
    return _to_gacha(dto)


@router.delete(_gacha_path("/{gacha_id}"), status_code=status.HTTP_204_NO_CONTENT)
def delete_gacha(*, ledger_id: int, gacha_id: int, use_case: DeleteGachaDep, principal: PointManager) -> None:
    """Delete a machine. Its draws and the points spent on them stay."""
    use_case.execute(ledger_id=ledger_id, gacha_id=gacha_id, account_id=principal.user_id)
    logger.info("gacha_deleted", extra={"ledger_id": ledger_id, "gacha_id": gacha_id})


@router.post(
    _gacha_path("/{gacha_id}/draws"), status_code=status.HTTP_201_CREATED, response_model=GachaDrawResultResponse
)
def draw_gacha(
    *, ledger_id: int, gacha_id: int, body: GachaDrawRequest, use_case: DrawGachaDep, principal: GachaDrawer
) -> GachaDrawResultResponse:
    """Draw once: spend ``price`` from the ledger and win one prize, picked on the server.

    Resending the same ``idempotency_key`` returns the draw already made (no second draw).
    A balance below the price is 409 ``insufficient_balance``.
    """
    result = use_case.execute(
        DrawGachaCommand(
            ledger_id=ledger_id,
            gacha_id=gacha_id,
            account_id=principal.user_id,
            idempotency_key=body.idempotency_key,
        )
    )
    logger.info(
        "gacha_drawn",
        extra={"ledger_id": ledger_id, "gacha_id": gacha_id, "draw_id": result.draw.id, "miss": result.draw.is_miss},
    )
    return GachaDrawResultResponse(draw=_to_draw(result.draw), balance=result.balance)


@router.post(
    _gacha_path("/{gacha_id}/bundles"), status_code=status.HTTP_201_CREATED, response_model=GachaBundleResultResponse
)
def draw_gacha_bundle(
    *, ledger_id: int, gacha_id: int, body: GachaDrawRequest, use_case: DrawGachaBundleDep, principal: GachaDrawer
) -> GachaBundleResultResponse:
    """Draw ten times and get one more free: eleven ordinary draws, ten paid (task #1047).

    The balance must cover ten draws (409 ``insufficient_balance``). Resending the same
    ``idempotency_key`` returns the bundle already drawn.
    """
    result = use_case.execute(
        DrawGachaCommand(
            ledger_id=ledger_id,
            gacha_id=gacha_id,
            account_id=principal.user_id,
            idempotency_key=body.idempotency_key,
        )
    )
    logger.info("gacha_bundle_drawn", extra={"ledger_id": ledger_id, "gacha_id": gacha_id, "draws": len(result.draws)})
    return GachaBundleResultResponse(draws=[_to_draw(draw) for draw in result.draws], balance=result.balance)


@router.post(_gacha_path("/{gacha_id}/trials"), response_model=GachaTrialResponse)
def try_gacha(*, ledger_id: int, gacha_id: int, use_case: TryGachaDep, principal: PointManager) -> GachaTrialResponse:
    """A parent's trial draw: a prize picked the same way, with nothing spent or recorded."""
    dto = use_case.execute(ledger_id=ledger_id, gacha_id=gacha_id, account_id=principal.user_id)
    logger.info("gacha_tried", extra={"ledger_id": ledger_id, "gacha_id": gacha_id, "miss": dto.is_miss})
    return GachaTrialResponse(gacha_name=dto.gacha_name, prize_name=dto.prize_name, is_miss=dto.is_miss)


@router.put(_draw_path("/{draw_id}/handed-over"), response_model=GachaDrawResponse)
def hand_over_gacha_prize(
    *, ledger_id: int, draw_id: int, use_case: HandOverGachaPrizeDep, principal: PointManager
) -> GachaDrawResponse:
    """Mark the won prize as handed over. A miss is 409 ``miss_cannot_be_handed_over``."""
    dto = use_case.execute(
        HandOverCommand(ledger_id=ledger_id, draw_id=draw_id, account_id=principal.user_id, handed_over=True)
    )
    logger.info("gacha_prize_handed_over", extra={"ledger_id": ledger_id, "draw_id": draw_id})
    return _to_draw(dto)


@router.delete(_draw_path("/{draw_id}/handed-over"), response_model=GachaDrawResponse)
def take_back_gacha_hand_over(
    *, ledger_id: int, draw_id: int, use_case: HandOverGachaPrizeDep, principal: PointManager
) -> GachaDrawResponse:
    """Take the "handed over" mark back (a mis-tap)."""
    dto = use_case.execute(
        HandOverCommand(ledger_id=ledger_id, draw_id=draw_id, account_id=principal.user_id, handed_over=False)
    )
    logger.info("gacha_prize_hand_over_taken_back", extra={"ledger_id": ledger_id, "draw_id": draw_id})
    return _to_draw(dto)


__all__ = ["router"]
