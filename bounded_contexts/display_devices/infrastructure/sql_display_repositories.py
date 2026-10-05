"""``IDisplayPairingRepository`` / ``IDisplayCredentialRepository`` の SQLAlchemy 実装。"""

from __future__ import annotations

from collections.abc import Set
from datetime import datetime

from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from bounded_contexts.display_devices.domain.entities.display_pairing import DisplayPairing
from bounded_contexts.display_devices.domain.repositories.display_credential_repository import (
    DisplayCredential,
    IDisplayCredentialRepository,
)
from bounded_contexts.display_devices.domain.repositories.display_pairing_repository import (
    IDisplayPairingRepository,
)
from bounded_contexts.display_devices.infrastructure.display_devices_models import (
    DisplayCredentialRecord,
    DisplayPairingRecord,
)


class SqlDisplayPairingRepository(IDisplayPairingRepository):
    def __init__(self, session: Session) -> None:
        self._session = session

    def add(self, *, user_code_hash: str, device_code_hash: str, expires_at: datetime) -> DisplayPairing:
        row = DisplayPairingRecord(
            user_code_hash=user_code_hash,
            device_code_hash=device_code_hash,
            expires_at=expires_at,
        )
        self._session.add(row)
        self._session.flush()
        return _to_pairing(row)

    def is_user_code_in_use(self, user_code_hash: str) -> bool:
        return self.find_by_user_code(user_code_hash) is not None

    def find_by_user_code(self, user_code_hash: str) -> DisplayPairing | None:
        row = self._session.scalar(
            select(DisplayPairingRecord).where(DisplayPairingRecord.user_code_hash == user_code_hash)
        )
        return _to_pairing(row) if row else None

    def find_by_device_code(self, device_code_hash: str) -> DisplayPairing | None:
        row = self._session.scalar(
            select(DisplayPairingRecord).where(DisplayPairingRecord.device_code_hash == device_code_hash)
        )
        return _to_pairing(row) if row else None

    def mark_approved(self, *, pairing_id: int, account_id: int, approved_at: datetime) -> None:
        row = self._require(pairing_id)
        row.approved_account_id = account_id
        row.approved_at = approved_at
        self._session.flush()

    def mark_claimed(self, *, pairing_id: int, claimed_at: datetime) -> None:
        row = self._require(pairing_id)
        row.claimed_at = claimed_at
        self._session.flush()

    def delete_expired_before(self, moment: datetime) -> None:
        self._session.execute(delete(DisplayPairingRecord).where(DisplayPairingRecord.expires_at < moment))

    def _require(self, pairing_id: int) -> DisplayPairingRecord:
        row = self._session.get(DisplayPairingRecord, pairing_id)
        if row is None:  # 同じ要求の中で引いた行なので通常は起きない
            raise ValueError(f"pairing not found: {pairing_id}")
        return row


class SqlDisplayCredentialRepository(IDisplayCredentialRepository):
    def __init__(self, session: Session) -> None:
        self._session = session

    def replace(self, *, account_id: int, credential_hash: str, issued_at: datetime) -> None:
        row = self._session.get(DisplayCredentialRecord, account_id)
        if row is None:
            row = DisplayCredentialRecord(account_id=account_id)
            self._session.add(row)
        row.credential_hash = credential_hash
        row.created_at = issued_at
        row.last_used_at = issued_at
        self._session.flush()

    def find_by_hash(self, credential_hash: str) -> DisplayCredential | None:
        row = self._session.scalar(
            select(DisplayCredentialRecord).where(DisplayCredentialRecord.credential_hash == credential_hash)
        )
        if row is None:
            return None
        return DisplayCredential(account_id=row.account_id, created_at=row.created_at, last_used_at=row.last_used_at)

    def touch(self, *, account_id: int, used_at: datetime) -> None:
        row = self._session.get(DisplayCredentialRecord, account_id)
        if row is not None:
            row.last_used_at = used_at
            self._session.flush()

    def delete(self, account_id: int) -> None:
        self._session.execute(delete(DisplayCredentialRecord).where(DisplayCredentialRecord.account_id == account_id))

    def account_ids(self) -> Set[int]:
        return frozenset(self._session.scalars(select(DisplayCredentialRecord.account_id)).all())

    def last_used(self) -> dict[int, datetime]:
        rows = self._session.execute(
            select(DisplayCredentialRecord.account_id, DisplayCredentialRecord.last_used_at)
        ).all()
        return {int(account_id): used_at for account_id, used_at in rows}


def _to_pairing(row: DisplayPairingRecord) -> DisplayPairing:
    return DisplayPairing(
        id=row.id,
        expires_at=row.expires_at,
        created_at=row.created_at,
        approved_account_id=row.approved_account_id,
        claimed_at=row.claimed_at,
    )


__all__ = ["SqlDisplayCredentialRepository", "SqlDisplayPairingRepository"]
