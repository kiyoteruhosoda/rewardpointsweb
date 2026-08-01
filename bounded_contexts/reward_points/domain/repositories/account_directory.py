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
    def create_account(
        self, *, username: str, password: str, role: FamilyRole, display_name: str | None = None
    ) -> AccountRef:
        """招待の受諾でアカウントを作る。

        メールアドレスは受け取らない。子アカウントはメールアドレスを持たない
        ことを前提とする（ADR-0011）。付与するアプリケーションロールは
        *role* から実装側が決める。

        *display_name* は本人が名乗る名前。省略・空文字ならログイン識別子を
        表示名にする。家族の中での呼び名（membership の display_name）とは
        別物で、こちらはアカウントそのものの表示名（ADR-0010）。
        """

    @abstractmethod
    def issue_temporary_password(self, account_id: int) -> TemporaryPassword:
        """一時パスワードを発行し、次回ログイン後の変更を必須にする。"""

    @abstractmethod
    def grant_guardian_permissions(self, account_id: int) -> None:
        """アカウントへ、親（メンバー）と同じアプリケーションロールを与える。

        子のロールのままだと家族の作成もポイントの記録もできないため、独立の
        成立（ADR-0014）で呼ぶ。既に保護者相当の scope を全て持つ場合は
        ロール構成へ触れない。
        """

    @abstractmethod
    def delete_account(self, account_id: int) -> None:
        """除名された子のアカウントを削除する（ADR-0018）。

        子アカウントは招待の受諾で生まれ、家族の参加としてだけ存在する。
        除名（台帳が空の場合に限る — ADR-0013）で家族との縁が切れたら、
        アカウントも残さない。
        """


__all__ = ["AccountRef", "IAccountDirectory", "IAccountProvisioning", "TemporaryPassword"]
