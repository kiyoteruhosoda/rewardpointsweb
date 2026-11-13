"""SQLAlchemy implementation of ``IFamilyInvitationRepository``.

Invitation codes are never stored in plaintext; only their SHA-256 hash is stored (same as
password reset tokens). Knowledge of hashing stays in this layer; the domain only knows
the plaintext.
"""

from __future__ import annotations

import hashlib
import secrets
from datetime import datetime
from typing import Any, cast

from sqlalchemy import delete, select, update
from sqlalchemy.engine import CursorResult
from sqlalchemy.orm import Session

from bounded_contexts.reward_points.domain.entities.family_invitation import FamilyInvitation
from bounded_contexts.reward_points.domain.repositories.family_invitation_repository import (
    IFamilyInvitationRepository,
    IssuedInvitation,
)
from bounded_contexts.reward_points.domain.value_objects.family_role import FamilyRole
from bounded_contexts.reward_points.infrastructure.reward_points_models import FamilyInvitationModel

# Children type these by hand, so use alphanumerics without confusable characters (0/O, 1/I/l).
_CODE_ALPHABET = "ABCDEFGHJKMNPQRSTUVWXYZ23456789"
_CODE_LENGTH = 10


def _hash_code(code: str) -> str:
    return hashlib.sha256(code.strip().upper().encode()).hexdigest()


def _generate_code() -> str:
    return "".join(secrets.choice(_CODE_ALPHABET) for _ in range(_CODE_LENGTH))


class SqlFamilyInvitationRepository(IFamilyInvitationRepository):
    def __init__(self, session: Session) -> None:
        self._session = session

    def issue(
        self,
        *,
        family_id: int,
        role: FamilyRole,
        target_membership_id: int | None,
        expires_at: datetime,
    ) -> IssuedInvitation:
        code = _generate_code()
        row = FamilyInvitationModel(
            family_id=family_id,
            code_hash=_hash_code(code),
            role=role.value,
            target_membership_id=target_membership_id,
            expires_at=expires_at,
        )
        self._session.add(row)
        self._session.flush()
        return IssuedInvitation(invitation=_to_invitation(row), code=code)

    def find_by_code(self, code: str) -> FamilyInvitation | None:
        row = self._session.scalar(
            select(FamilyInvitationModel).where(FamilyInvitationModel.code_hash == _hash_code(code))
        )
        return _to_invitation(row) if row else None

    def list_pending(self, family_id: int, *, now: datetime) -> list[FamilyInvitation]:
        rows = self._session.scalars(
            select(FamilyInvitationModel)
            .where(
                FamilyInvitationModel.family_id == family_id,
                FamilyInvitationModel.used_at.is_(None),
                FamilyInvitationModel.expires_at > now,
            )
            .order_by(FamilyInvitationModel.id)
        ).all()
        return [_to_invitation(row) for row in rows]

    def find_in_family(self, *, family_id: int, invitation_id: int) -> FamilyInvitation | None:
        row = self._session.scalar(
            select(FamilyInvitationModel).where(
                FamilyInvitationModel.id == invitation_id,
                FamilyInvitationModel.family_id == family_id,
            )
        )
        return _to_invitation(row) if row else None

    def consume(self, code: str, *, now: datetime) -> FamilyInvitation | None:
        """Do "mark as used if still usable" in one step with a conditional UPDATE.

        Because ``used_at IS NULL`` is part of the condition, a second concurrent request
        updates 0 rows (the first update holds the row lock and the condition is re-evaluated
        after release). Returns the invitation only if the update succeeded.
        """
        code_hash = _hash_code(code)
        # The number of updated rows answers "did we win". ``Session.execute`` is typed to
        # return ``Result``, but for UPDATE it returns a ``CursorResult``.
        updated = cast(
            "CursorResult[Any]",
            self._session.execute(
                update(FamilyInvitationModel)
                .where(
                    FamilyInvitationModel.code_hash == code_hash,
                    FamilyInvitationModel.used_at.is_(None),
                    FamilyInvitationModel.expires_at > now,
                )
                .values(used_at=now)
                .execution_options(synchronize_session=False)
            ),
        )
        if updated.rowcount != 1:
            return None
        row = self._session.scalar(select(FamilyInvitationModel).where(FamilyInvitationModel.code_hash == code_hash))
        return _to_invitation(row) if row else None

    def delete(self, invitation_id: int) -> None:
        self._session.execute(delete(FamilyInvitationModel).where(FamilyInvitationModel.id == invitation_id))


def _to_invitation(row: FamilyInvitationModel) -> FamilyInvitation:
    return FamilyInvitation(
        id=row.id,
        family_id=row.family_id,
        role=FamilyRole(row.role),
        target_membership_id=row.target_membership_id,
        expires_at=row.expires_at,
        used_at=row.used_at,
        created_at=row.created_at,
    )


__all__ = ["SqlFamilyInvitationRepository"]
