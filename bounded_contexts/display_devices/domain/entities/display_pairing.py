"""ペアリング 1 回（表示端末が確認コードを出してから、資格情報を受け取るまで）。

状態は 4 つで、列から導く（状態の列は持たない）。

============ ============================================
まだ         承認も受け取りもされておらず、期限内
承認済み     ``approved_account_id`` が入り、まだ受け取られていない
受け取り済み ``claimed_at`` が入った。もう使えない
期限切れ     ``expires_at`` を過ぎた（承認済みでも受け取れない）
============ ============================================
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime


@dataclass(frozen=True, kw_only=True)
class DisplayPairing:
    id: int
    expires_at: datetime
    created_at: datetime
    #: 承認で生まれた表示アカウント。承認前は ``None``
    approved_account_id: int | None = None
    claimed_at: datetime | None = None

    def is_expired(self, now: datetime) -> bool:
        return now >= self.expires_at

    @property
    def is_claimed(self) -> bool:
        return self.claimed_at is not None

    @property
    def is_approved(self) -> bool:
        return self.approved_account_id is not None

    def can_be_approved(self, now: datetime) -> bool:
        return not self.is_expired(now) and not self.is_approved and not self.is_claimed


__all__ = ["DisplayPairing"]
