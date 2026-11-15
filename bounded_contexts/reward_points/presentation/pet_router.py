"""API for choosing the pet on a ledger (ADR-0061).

The pet itself is read with the ledger (``GET .../ledgers/{id}`` returns ``pet``). Choosing
the species needs ``pet:choose`` (parents and children), and the family role decides which
ledger: parents any child's, a child their own.
"""

from __future__ import annotations

import logging
from typing import Annotated

from fastapi import APIRouter, Depends

from bounded_contexts.reward_points.application.use_cases.choose_pet import ChoosePetCommand, ChoosePetUseCase
from bounded_contexts.reward_points.presentation.dependencies import AccessDep, PetRepoDep, TransactionRepoDep
from bounded_contexts.reward_points.presentation.router import to_pet_response
from bounded_contexts.reward_points.presentation.schemas import PetChooseRequest, PetResponse
from presentation.fastapi.dependencies.auth import require_permission
from shared.application.authenticated_principal import AuthenticatedPrincipal

router = APIRouter(prefix="/api/families", tags=["reward-points"])
logger = logging.getLogger(__name__)

PetChooser = Annotated[AuthenticatedPrincipal, Depends(require_permission("pet:choose"))]


def get_choose_pet_use_case(access: AccessDep, pets: PetRepoDep, transactions: TransactionRepoDep) -> ChoosePetUseCase:
    return ChoosePetUseCase(access, pets, transactions)


ChoosePetDep = Annotated[ChoosePetUseCase, Depends(get_choose_pet_use_case)]


@router.put("/{family_id}/ledgers/{ledger_id}/pet", response_model=PetResponse)
def choose_pet(*, ledger_id: int, body: PetChooseRequest, use_case: ChoosePetDep, principal: PetChooser) -> PetResponse:
    """Choose or change the pet's species. Growth comes from the ledger and does not change."""
    dto = use_case.execute(ChoosePetCommand(ledger_id=ledger_id, account_id=principal.user_id, species=body.species))
    logger.info("pet_chosen", extra={"ledger_id": ledger_id, "species": body.species.value})
    return to_pet_response(dto)


__all__ = ["router"]
