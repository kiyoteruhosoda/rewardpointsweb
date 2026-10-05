"""端末の資格情報から、どの表示アカウントとして入るかを決める（ADR-0047）。

⚠ **この口は毎回 DB を引く**（ADR-0037 の決定 3・4「出し直す経路は引く」）。外された
端末の資格情報は行ごと消えているので、次の取り直しで断られる。
"""

from __future__ import annotations

from collections.abc import Set
from datetime import datetime

from bounded_contexts.display_devices.domain.exceptions import (
    DeviceCredentialExpiredError,
    InvalidDeviceCredentialError,
)
from bounded_contexts.display_devices.domain.repositories.display_credential_repository import (
    IDisplayCredentialRepository,
)
from bounded_contexts.display_devices.domain.services import pairing_secrets
from bounded_contexts.display_devices.domain.services.pairing_rules import CREDENTIAL_IDLE_LIMIT
from shared.kernel.timestamps import utcnow


class OpenDisplaySessionUseCase:
    def __init__(self, credentials: IDisplayCredentialRepository) -> None:
        self._credentials = credentials

    def execute(self, device_credential: str) -> int:
        """表示アカウントの ID を返し、最後に使った日時を書く。

        使われないまま :data:`CREDENTIAL_IDLE_LIMIT` を過ぎていたら資格情報を消し、
        :class:`DeviceCredentialExpiredError` で知らせる（端末を外すのは呼び出し側）。
        """
        now = utcnow()
        found = self._credentials.find_by_hash(pairing_secrets.hash_secret(device_credential))
        if found is None:
            raise InvalidDeviceCredentialError
        if found.last_used_at + CREDENTIAL_IDLE_LIMIT < now:
            self._credentials.delete(found.account_id)
            raise DeviceCredentialExpiredError(found.account_id)
        self._credentials.touch(account_id=found.account_id, used_at=now)
        return found.account_id


class DescribeDisplayCredentialsUseCase:
    """資格情報の棚卸し（入れる手段・最後に使った日時）。"""

    def __init__(self, credentials: IDisplayCredentialRepository) -> None:
        self._credentials = credentials

    def holders(self) -> Set[int]:
        return self._credentials.account_ids()

    def last_used(self) -> dict[int, datetime]:
        return self._credentials.last_used()


__all__ = ["DescribeDisplayCredentialsUseCase", "OpenDisplaySessionUseCase"]
