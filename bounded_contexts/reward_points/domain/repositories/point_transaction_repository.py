"""台帳トランザクションの永続化インターフェース。

追記専用のため、更新・行単位の削除の口は用意しない（ADR-0010）。唯一の例外は
独立の成立時に台帳ごと消す :meth:`IPointTransactionRepository.delete_by_ledger`
（ADR-0014）。
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import datetime

from bounded_contexts.reward_points.domain.entities.point_transaction import PointTransaction


@dataclass(frozen=True, kw_only=True)
class NewTransaction:
    """まだ台帳へ書かれていない 1 行。

    書き込みに必要な値をまとめて 1 つの引数にする（加算・消費・打ち消し・訂正で
    渡すものが同じなので、書き込み口も 1 つで足りる）。
    """

    ledger_id: int
    amount: int
    reason: str
    # 毎日のボーナス（ADR-0024）は誰の操作でもないので ``None`` で書く。
    # 画面には記録者の欄が空のまま並ぶ
    granted_by_membership_id: int | None
    occurred_at: datetime
    idempotency_key: str
    reversal_of_id: int | None = None
    # 訂正後の行なら、言い直した相手の ID（ADR-0022）
    corrects_id: int | None = None


class IPointTransactionRepository(ABC):
    @abstractmethod
    def list_by_ledger(self, ledger_id: int) -> list[PointTransaction]:
        """発生日時の新しい順。"""

    @abstractmethod
    def list_by_ledgers(self, ledger_ids: Sequence[int]) -> Mapping[int, list[PointTransaction]]:
        """台帳 ID -> 履歴。一覧の残高計算で 1 件ずつ引かないための入口。"""

    @abstractmethod
    def find_in_ledger(self, *, ledger_id: int, transaction_id: int) -> PointTransaction | None: ...

    @abstractmethod
    def find_reversal_of(self, transaction_id: int) -> PointTransaction | None:
        """すでに打ち消されているかを調べる（``reversal_of_id`` は UNIQUE）。"""

    @abstractmethod
    def append(self, new_transaction: NewTransaction) -> PointTransaction:
        """1 行追記する。

        ``UNIQUE (ledger_id, idempotency_key)`` に抵触した場合はエラーとせず、
        既存のレコードを返す（ADR-0010）。
        """

    @abstractmethod
    def count_by_ledger(self, ledger_id: int) -> int: ...

    @abstractmethod
    def delete_by_ledger(self, ledger_id: int) -> None:
        """台帳の全レコードを消す。

        追記専用（ADR-0010）の唯一の例外で、独立の成立時にだけ呼ぶ（ADR-0014）。
        行単位の削除は今後も用意しない。
        """

    @abstractmethod
    def frequent_reasons(self, *, family_id: int, limit: int) -> list[str]:
        """その家族で使われた理由を、頻度の高い順に返す。

        入力の手間を減らすための候補であり、認可の対象は家族。他家族の理由は
        含めない（``family_id`` で絞る）。
        """


__all__ = ["IPointTransactionRepository", "NewTransaction"]
