"""共有相手（ログインアカウント）を引くためのインターフェース。

ユーザーそのものはこのコンテキストの持ち物ではないため、必要な範囲だけを
ポートとして切り出す。共有相手の指定は **メールアドレス** で行い、ユーザー一覧を
このコンテキストへ渡さない。一覧を渡すと、``user:manage`` を持たない管理者にも
全アカウントが見えてしまう。
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import Mapping, Sequence
from dataclasses import dataclass


@dataclass(frozen=True, kw_only=True)
class ShareTarget:
    """共有相手の表示に必要な最小限（認可には使わない）。"""

    user_id: int
    email: str
    username: str


class IShareTargetDirectory(ABC):
    @abstractmethod
    def find_by_email(self, email: str) -> ShareTarget | None: ...

    @abstractmethod
    def describe(self, user_ids: Sequence[int]) -> Mapping[int, ShareTarget]:
        """ユーザー ID -> 表示用の情報。見つからない ID は結果に含まれない。"""


__all__ = ["IShareTargetDirectory", "ShareTarget"]
