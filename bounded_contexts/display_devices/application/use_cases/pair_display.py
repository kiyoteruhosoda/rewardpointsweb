"""表示端末のペアリング（ADR-0047。RFC 8628 に倣う）。

1. 端末が始める（:class:`StartPairingUseCase`）——確認コードと端末の秘密を受け取る
2. 運用管理者が確認コードで承認する（:class:`ApprovePairingUseCase`）——表示アカウントが生まれる
3. 端末が端末の秘密で受け取る（:class:`ClaimPairingUseCase`）——端末の資格情報を 1 度だけ受け取る

表示アカウントを作るのは reward_points（家族の参加として作る）。承認はそれを
``enroll`` として受け取り、確認コードが使えると分かってから呼ぶ。
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

from bounded_contexts.display_devices.domain.entities.display_pairing import DisplayPairing
from bounded_contexts.display_devices.domain.exceptions import (
    AuthorizationPendingError,
    ExpiredTokenError,
    PairingExpiredError,
    PairingNotFoundError,
)
from bounded_contexts.display_devices.domain.repositories.display_credential_repository import (
    IDisplayCredentialRepository,
)
from bounded_contexts.display_devices.domain.repositories.display_pairing_repository import (
    IDisplayPairingRepository,
)
from bounded_contexts.display_devices.domain.services import pairing_secrets
from bounded_contexts.display_devices.domain.services.pairing_rules import (
    PAIRING_RETENTION,
    PAIRING_TTL,
    POLL_INTERVAL_SECONDS,
)
from shared.kernel.timestamps import utcnow

# 確認コードが残っている行と重なったときに引き直す回数。31 種 8 字なので、まず起きない
_USER_CODE_ATTEMPTS = 5


@dataclass(frozen=True, kw_only=True)
class StartedPairing:
    """端末に返すもの。平文はこの 1 回しか取り出せない。"""

    #: 画面に出す確認コード（``KQ7M-3XPA``）
    user_code: str
    #: 端末だけが知る秘密。受け取りに要る
    device_code: str
    expires_in: int
    interval: int


class StartPairingUseCase:
    def __init__(self, pairings: IDisplayPairingRepository) -> None:
        self._pairings = pairings

    def execute(self) -> StartedPairing:
        now = utcnow()
        # 誰でも始められる口なので、古い行はここで掃除して溜めない
        self._pairings.delete_expired_before(now - PAIRING_RETENTION)
        user_code = self._fresh_user_code()
        device_code = pairing_secrets.new_secret()
        self._pairings.add(
            user_code_hash=pairing_secrets.hash_secret(user_code),
            device_code_hash=pairing_secrets.hash_secret(device_code),
            expires_at=now + PAIRING_TTL,
        )
        return StartedPairing(
            user_code=pairing_secrets.format_user_code(user_code),
            device_code=device_code,
            expires_in=int(PAIRING_TTL.total_seconds()),
            interval=POLL_INTERVAL_SECONDS,
        )

    def _fresh_user_code(self) -> str:
        for _ in range(_USER_CODE_ATTEMPTS):
            code = pairing_secrets.new_user_code()
            if not self._pairings.is_user_code_in_use(pairing_secrets.hash_secret(code)):
                return code
        raise RuntimeError("could not find a free pairing code")


class ApprovePairingUseCase:
    def __init__(self, pairings: IDisplayPairingRepository) -> None:
        self._pairings = pairings

    def execute(self, *, user_code: str, enroll: Callable[[], int]) -> int:
        """確認コードを承認し、``enroll`` が作った表示アカウントを結び付ける。

        ``enroll`` は確認コードが使えると分かってから 1 度だけ呼ぶ。打ち間違いで
        表示アカウントが生まれないようにするため。結び付けたアカウントの ID を返す。
        """
        pairing = self._approvable(user_code)
        account_id = enroll()
        self._pairings.mark_approved(pairing_id=pairing.id, account_id=account_id, approved_at=utcnow())
        return account_id

    def _approvable(self, user_code: str) -> DisplayPairing:
        normalized = pairing_secrets.normalize_user_code(user_code)
        if normalized is None:
            raise PairingNotFoundError
        pairing = self._pairings.find_by_user_code(pairing_secrets.hash_secret(normalized))
        if pairing is None or pairing.is_approved or pairing.is_claimed:
            raise PairingNotFoundError
        if not pairing.can_be_approved(utcnow()):
            raise PairingExpiredError
        return pairing


class ClaimPairingUseCase:
    def __init__(self, pairings: IDisplayPairingRepository, credentials: IDisplayCredentialRepository) -> None:
        self._pairings = pairings
        self._credentials = credentials

    def execute(self, device_code: str) -> str:
        """承認済みなら端末の資格情報（平文）を 1 度だけ返す。"""
        now = utcnow()
        pairing = self._pairings.find_by_device_code(pairing_secrets.hash_secret(device_code))
        if pairing is None or pairing.is_claimed or pairing.is_expired(now):
            raise ExpiredTokenError
        if pairing.approved_account_id is None:
            raise AuthorizationPendingError
        credential = pairing_secrets.new_secret()
        self._credentials.replace(
            account_id=pairing.approved_account_id,
            credential_hash=pairing_secrets.hash_secret(credential),
            issued_at=now,
        )
        self._pairings.mark_claimed(pairing_id=pairing.id, claimed_at=now)
        return credential


__all__ = [
    "ApprovePairingUseCase",
    "ClaimPairingUseCase",
    "StartPairingUseCase",
    "StartedPairing",
]
