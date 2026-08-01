"""アカウントを引く／作るためのポート。

アカウントそのものはこのコンテキストの持ち物ではないため、必要な範囲だけを
切り出す。読み取り（:class:`IAccountDirectory`）と書き込み
（:class:`IAccountProvisioning`）を分けるのは、招待の受諾のように
アカウントを作る経路だけが後者を必要とするため。
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import datetime

from bounded_contexts.reward_points.domain.value_objects.family_role import FamilyRole


@dataclass(frozen=True, kw_only=True)
class AccountRef:
    """参加者の表示に必要な最小限（認可には使わない）。"""

    account_id: int
    username: str
    display_name: str
    # メールアドレスは任意項目（ADR-0011）。持たないアカウントもある
    email: str | None


@dataclass(frozen=True, kw_only=True)
class TemporaryPassword:
    """親が発行した一時パスワード。平文はこの 1 回しか取り出せない。"""

    password: str
    expires_at: datetime


class IAccountDirectory(ABC):
    @abstractmethod
    def describe(self, account_ids: Sequence[int]) -> Mapping[int, AccountRef]:
        """アカウント ID -> 表示用の情報。見つからない ID は結果に含まれない。"""


class IAccountProvisioning(ABC):
    @abstractmethod
    def is_username_taken(self, username: str) -> bool: ...

    @abstractmethod
    def create_account(self, *, username: str, password: str, role: FamilyRole) -> AccountRef:
        """招待の受諾でアカウントを作る。

        メールアドレスは受け取らない。子アカウントはメールアドレスを持たない
        ことを前提とする（ADR-0011）。付与するアプリケーションロールは
        *role* から実装側が決める。
        """

    @abstractmethod
    def issue_temporary_password(self, account_id: int) -> TemporaryPassword:
        """一時パスワードを発行し、次回ログイン後の変更を必須にする。"""

    @abstractmethod
    def grant_guardian_permissions(self, account_id: int) -> None:
        """独立したアカウントへ、親（メンバー）と同じアプリケーションロールを与える。

        独立後は自分の家族を作れる必要がある（ADR-0014）。子の閲覧専用ロールの
        ままだと家族の作成もポイントの記録もできない。
        """


__all__ = ["AccountRef", "IAccountDirectory", "IAccountProvisioning", "TemporaryPassword"]
