"""SQLAlchemy implementation of ``IPetCareRepository`` (ADR-0061, task #1128)."""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from bounded_contexts.reward_points.domain.entities.pet_care import PetCare, PetCareKind
from bounded_contexts.reward_points.domain.repositories.pet_care_repository import IPetCareRepository, NewPetCare
from bounded_contexts.reward_points.infrastructure.reward_points_models import PetCareModel


class SqlPetCareRepository(IPetCareRepository):
    def __init__(self, session: Session) -> None:
        self._session = session

    def record(self, care: NewPetCare) -> None:
        self._session.add(
            PetCareModel(
                pet_id=care.pet_id,
                kind=care.kind.value,
                cared_at=care.cared_at,
                care_day=care.care_day,
                cared_by_membership_id=care.cared_by_membership_id,
            )
        )
        self._session.flush()

    def cared_since(self, pet_id: int, since: datetime) -> list[PetCare]:
        rows = self._session.scalars(
            select(PetCareModel)
            .where(PetCareModel.pet_id == pet_id, PetCareModel.cared_at >= since)
            .order_by(PetCareModel.cared_at, PetCareModel.id)
        ).all()
        return [_to_care(row) for row in rows]

    def last(self, pet_id: int) -> PetCare | None:
        row = self._session.scalar(
            select(PetCareModel)
            .where(PetCareModel.pet_id == pet_id)
            .order_by(PetCareModel.cared_at.desc(), PetCareModel.id.desc())
            .limit(1)
        )
        return _to_care(row) if row is not None else None

    def last_of_kind(self, pet_id: int, kind: PetCareKind) -> datetime | None:
        last: datetime | None = self._session.scalar(
            select(func.max(PetCareModel.cared_at)).where(
                PetCareModel.pet_id == pet_id, PetCareModel.kind == kind.value
            )
        )
        return last

    def days_cared(self, pet_id: int) -> int:
        count = self._session.scalar(
            select(func.count(func.distinct(PetCareModel.care_day))).where(PetCareModel.pet_id == pet_id)
        )
        return int(count or 0)


def _to_care(row: PetCareModel) -> PetCare:
    return PetCare(kind=PetCareKind(row.kind), cared_at=row.cared_at)


__all__ = ["SqlPetCareRepository"]
