"""``IFamilyInvitationRepository`` の SQLAlchemy 実装。

招待コードは平文を保存せず SHA-256 ハッシュだけを保存する（パスワードリセット
トークンと同じ扱い）。ハッシュ化の知識はこの層に閉じ、ドメイン側は平文しか
知らない。
"""

from __future__ import annotations

import hashlib
import secrets
from datetime import datetime

from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from bounded_contexts.reward_points.domain.entities.family_invitation import FamilyInvitation
from bounded_contexts.reward_points.domain.repositories.family_invitation_repository import (
    IFamilyInvitationRepository,
    IssuedInvitation,
)
from bounded_contexts.reward_points.domain.value_objects.family_role import FamilyRole
from bounded_contexts.reward_points.infrastructure.reward_points_models import FamilyInvitationModel

# 子どもが手で入力する前提のため、紛らわしい文字（0/O・1/I/l）を外した英数字を使う。
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

    def mark_used(self, *, invitation_id: int, used_at: datetime) -> None:
        row = self._session.get(FamilyInvitationModel, invitation_id)
        if row is not None:
            row.used_at = used_at
            self._session.flush()

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
