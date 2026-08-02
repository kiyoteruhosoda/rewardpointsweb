"""記録を訂正する（打ち消し ＋ 正しい内容の書き直し）。

台帳は追記専用なので、入力の間違いを直しても元の行は書き換えない。1 回の要求で
**2 行**を足す（ADR-0022）。

1. 元の行を打ち消す行（``reversal_of_id``）— 打ち消しだけを行う既存の操作と同じもの
2. 正しい内容の行（``corrects_id``）— どの行の言い直しかを示す

2 行を分けて送らせない理由は、片方だけが成功した状態を利用者に見せないため。
1 つのトランザクションの中で両方書き、どちらかが落ちればどちらも残らない。

送り直しは「すでに打ち消し済み」として断る（409）。打ち消しの操作と同じで、
二重に効いてしまうより、効かずに知らせる方を選ぶ。

冪等キーは 2 行それぞれのために段階ごとへ分ける。区切り文字はこの分割の予約で、
クライアントの鍵には現れない（API で弾く）。それでも同じ鍵を別の記録の訂正へ
使い回されると分けた鍵が重なるため、打ち消しの行が本当に自分の対象を指して
いるかを書いた直後に確かめる。
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from bounded_contexts.reward_points.application.dto.ledger_dto import CorrectionDTO, just_written
from bounded_contexts.reward_points.application.family_access_resolver import FamilyAccessResolver
from bounded_contexts.reward_points.domain.entities.point_transaction import PointTransaction
from bounded_contexts.reward_points.domain.exceptions import (
    IdempotencyKeyReusedError,
    TransactionAlreadyReversedError,
    TransactionNotFoundError,
)
from bounded_contexts.reward_points.domain.repositories.point_transaction_repository import (
    IPointTransactionRepository,
    NewTransaction,
)
from bounded_contexts.reward_points.domain.value_objects.idempotency_key import IdempotencyKey
from shared.kernel.timestamps import as_naive_utc, utcnow

# 1 回の訂正が書く 2 行を、冪等キーの上で区別する（同じ鍵だと 2 行目が
# 1 行目の使い回しになる）
_REVERSAL_STEP = "reversal"
_CORRECTION_STEP = "correction"


@dataclass(frozen=True, kw_only=True)
class CorrectTransactionCommand:
    ledger_id: int
    transaction_id: int
    account_id: int
    amount: int
    reason: str
    # 未指定なら元の記録の発生日時を引き継ぐ（量の打ち間違いを直しただけで
    # 出来事が今日へ動いてしまわないように）
    occurred_at: datetime | None
    idempotency_key: str


class CorrectPointTransactionUseCase:
    def __init__(self, access: FamilyAccessResolver, transactions: IPointTransactionRepository) -> None:
        self._access = access
        self._transactions = transactions

    def execute(self, command: CorrectTransactionCommand) -> CorrectionDTO:
        found = self._access.modifiable_ledger(ledger_id=command.ledger_id, account_id=command.account_id)
        original = self._original(command)
        # 打ち消しより先に組み立てる。打ち消しの行を訂正しようとしたとき、
        # 「打ち消しは打ち消せない」ではなく「打ち消しは訂正できない」と伝えるため
        corrected = original.plan_correction(
            amount=command.amount,
            reason=command.reason,
            occurred_at=as_naive_utc(command.occurred_at) if command.occurred_at else None,
        )
        undo = original.plan_reversal()
        key = IdempotencyKey(command.idempotency_key)
        actor = found.membership.id
        reversal = self._transactions.append(
            NewTransaction(
                ledger_id=undo.ledger_id,
                amount=undo.amount.value,
                reason=undo.reason.value,
                granted_by_membership_id=actor,
                # 打ち消したのは「いま」（元の出来事の日時は元の行が持っている）
                occurred_at=utcnow(),
                idempotency_key=key.for_step(_REVERSAL_STEP).value,
                reversal_of_id=undo.reversal_of_id,
            )
        )
        if reversal.reversal_of_id != undo.reversal_of_id:
            # 分けた鍵で既存の行が返った ＝ その鍵は別の訂正で使われている。
            # このまま進めると打ち消しを書かないまま訂正後の行だけが足され、
            # 元の記録と両方が残高に効いてしまう
            raise IdempotencyKeyReusedError
        correction = self._transactions.append(
            NewTransaction(
                ledger_id=corrected.ledger_id,
                amount=corrected.amount.value,
                reason=corrected.reason.value,
                granted_by_membership_id=actor,
                occurred_at=corrected.occurred_at,
                idempotency_key=key.for_step(_CORRECTION_STEP).value,
                corrects_id=corrected.corrects_id,
            )
        )
        name = found.membership.display_name_value
        return CorrectionDTO(
            reversal=just_written(reversal, granted_by=name),
            correction=just_written(correction, granted_by=name),
        )

    def _original(self, command: CorrectTransactionCommand) -> PointTransaction:
        original = self._transactions.find_in_ledger(ledger_id=command.ledger_id, transaction_id=command.transaction_id)
        if original is None:
            raise TransactionNotFoundError
        if self._transactions.find_reversal_of(original.id) is not None:
            # すでに打ち消されている行に足しても、元の内容へは戻せない。
            # 正しい内容は新しい記録として足してもらう
            raise TransactionAlreadyReversedError
        return original


__all__ = ["CorrectPointTransactionUseCase", "CorrectTransactionCommand"]
