"""クライアントが生成する冪等キー。

モバイルでの二重タップを台帳に二重登録させないための鍵で、台帳ごとに一意
（``UNIQUE (ledger_id, idempotency_key)``）。衝突はエラーにせず、既存の
レコードを返す（ADR-0010）。

1 回の操作が 2 行を書くことがある（訂正 ＝ 打ち消し ＋ 記録し直し。ADR-0022）。
このとき同じ鍵を 2 度使うと、2 行目が 1 行目の使い回しになってしまうため、
:meth:`IdempotencyKey.for_step` で段階ごとの鍵へ分ける。分けた後も上限に収まる
よう、受け取る鍵の上限は :data:`MAX_BASE_LENGTH` までとする。
"""

from __future__ import annotations

from dataclasses import dataclass

MAX_LENGTH = 64
STEP_SEPARATOR = "#"
MAX_STEP_LENGTH = 12
MAX_BASE_LENGTH = MAX_LENGTH - len(STEP_SEPARATOR) - MAX_STEP_LENGTH


@dataclass(frozen=True)
class IdempotencyKey:
    value: str

    def __post_init__(self) -> None:
        if not self.value.strip():
            raise ValueError("Idempotency key cannot be empty")
        if len(self.value) > MAX_LENGTH:
            raise ValueError(f"Idempotency key cannot exceed {MAX_LENGTH} characters")

    def for_step(self, step: str) -> IdempotencyKey:
        """1 回の操作の中の、ある段階のための鍵。

        同じ要求を送り直したときに同じ値になることが要点で、段階どうしが
        違う値でありさえすればよい。
        """
        if not 0 < len(step) <= MAX_STEP_LENGTH:
            raise ValueError(f"Idempotency step must be 1..{MAX_STEP_LENGTH} characters")
        if len(self.value) > MAX_BASE_LENGTH:
            raise ValueError(f"Idempotency key cannot exceed {MAX_BASE_LENGTH} characters to be split by step")
        return IdempotencyKey(f"{self.value}{STEP_SEPARATOR}{step}")


__all__ = ["MAX_BASE_LENGTH", "MAX_LENGTH", "MAX_STEP_LENGTH", "STEP_SEPARATOR", "IdempotencyKey"]
