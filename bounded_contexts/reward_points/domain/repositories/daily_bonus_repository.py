"""毎日のボーナスの永続化インターフェース（ADR-0024）。

台帳 1 つにつき 1 件（``UNIQUE (ledger_id)``）。台帳が消えれば設定も消える
（家族の解散・参加者の削除・独立の成立）。
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import date

from bounded_contexts.reward_points.domain.entities.daily_bonus import DailyBonus


@dataclass(frozen=True, kw_only=True)
class DailyBonusDraft:
    """これから保存する設定。"""

    ledger_id: int
    amount: int
    reason: str
    #: 新しく作るときの「最初に渡す日」。すでにある設定では使わない
    starts_on: date


class IDailyBonusRepository(ABC):
    @abstractmethod
    def find_by_ledger(self, ledger_id: int) -> DailyBonus | None: ...

    @abstractmethod
    def list_for_ledgers(self, ledger_ids: Sequence[int]) -> list[DailyBonus]:
        """複数の台帳の設定をまとめて読む（家族設定の画面のため。ADR-0027）。

        設定は家族設定に並ぶので、参加者ごとに引き直すと家族の人数だけ往復が増える。
        """

    @abstractmethod
    def save(self, draft: DailyBonusDraft) -> DailyBonus:
        """台帳の設定を作る、または量と理由を書き換える。

        すでにある設定の ``starts_on`` と ``granted_through`` は動かさない。量を
        直しただけで、渡し終えた日まで無かったことになってはいけない。
        """

    @abstractmethod
    def delete_by_ledger(self, ledger_id: int) -> None:
        """設定を消す（＝毎日のボーナスをやめる）。台帳の履歴には触れない。"""

    @abstractmethod
    def list_due(self, today: date) -> list[DailyBonus]:
        """*today* の時点でまだ渡していない日がある設定。

        家族を跨いで返す（付与は家族の外側から回るため）。認可の対象ではない
        ので、呼べるのは付与のユースケースだけに保つ。
        """

    @abstractmethod
    def mark_granted_through(self, *, bonus_id: int, day: date) -> None:
        """*day* まで渡し終えたことを記録する。"""


__all__ = ["DailyBonusDraft", "IDailyBonusRepository"]
