"""API for choosing and caring for the pet on a ledger (ADR-0061).

The pet itself is read with the ledger (``GET .../ledgers/{id}`` returns ``pet``). Choosing
needs ``pet:choose`` and caring ``pet:care`` (parents and children); the family role decides
which ledger: parents any child's, a child their own. Display devices only look.
"""

from __future__ import annotations

import logging
from typing import Annotated

from fastapi import APIRouter, Depends

from bounded_contexts.reward_points.application.use_cases.care_for_pet import (
    CareForPetCommand,
    CareForPetUseCase,
    PetCareSources,
)
from bounded_contexts.reward_points.application.use_cases.choose_pet import ChoosePetCommand, ChoosePetUseCase
from bounded_contexts.reward_points.presentation.dependencies import (
    AccessDep,
    PetCareRepoDep,
    PetReaderDep,
    PetRepoDep,
    TransactionRepoDep,
    resolve_day_boundary,
)
from bounded_contexts.reward_points.presentation.router import to_pet_response
from bounded_contexts.reward_points.presentation.schemas import PetCareRequest, PetChooseRequest, PetResponse
from presentation.fastapi.dependencies.auth import require_permission
from shared.application.authenticated_principal import AuthenticatedPrincipal

router = APIRouter(prefix="/api/families", tags=["reward-points"])
logger = logging.getLogger(__name__)

PetChooser = Annotated[AuthenticatedPrincipal, Depends(require_permission("pet:choose"))]
PetCarer = Annotated[AuthenticatedPrincipal, Depends(require_permission("pet:care"))]


def get_choose_pet_use_case(
    *, access: AccessDep, pets: PetRepoDep, transactions: TransactionRepoDep, reader: PetReaderDep
) -> ChoosePetUseCase:
    return ChoosePetUseCase(access, pets, transactions, reader=reader)


ChoosePetDep = Annotated[ChoosePetUseCase, Depends(get_choose_pet_use_case)]


def get_pet_care_sources(pets: PetRepoDep, cares: PetCareRepoDep, transactions: TransactionRepoDep) -> PetCareSources:
    return PetCareSources(pets=pets, cares=cares, transactions=transactions)


def get_care_for_pet_use_case(
    access: AccessDep, sources: Annotated[PetCareSources, Depends(get_pet_care_sources)], reader: PetReaderDep
) -> CareForPetUseCase:
    return CareForPetUseCase(access, sources, boundary=resolve_day_boundary(), reader=reader)


CareForPetDep = Annotated[CareForPetUseCase, Depends(get_care_for_pet_use_case)]


@router.put("/{family_id}/ledgers/{ledger_id}/pet", response_model=PetResponse)
def choose_pet(*, ledger_id: int, body: PetChooseRequest, use_case: ChoosePetDep, principal: PetChooser) -> PetResponse:
    """Receive an egg of *species*: the first pet, or the next one after the current reached the final stage.

    While the current pet is growing its species cannot change (409 ``pet_already_chosen``).
    """
    dto = use_case.execute(ChoosePetCommand(ledger_id=ledger_id, account_id=principal.user_id, species=body.species))
    logger.info("pet_chosen", extra={"ledger_id": ledger_id, "species": body.species.value})
    return to_pet_response(dto)


@router.post("/{family_id}/ledgers/{ledger_id}/pet/cares", response_model=PetResponse)
def care_for_pet(*, ledger_id: int, body: PetCareRequest, use_case: CareForPetDep, principal: PetCarer) -> PetResponse:
    """Give the hatched pet a care (feed, pat, play, bath) and answer how it feels now.

    Free, and it never changes the balance or the growth. Before it hatches: 409 ``pet_not_hatched``.
    The same kind again within a short while is answered but not recorded.
    """
    dto = use_case.execute(CareForPetCommand(ledger_id=ledger_id, account_id=principal.user_id, kind=body.kind))
    logger.info("pet_cared_for", extra={"ledger_id": ledger_id, "kind": body.kind.value})
    return to_pet_response(dto)


__all__ = ["router"]
