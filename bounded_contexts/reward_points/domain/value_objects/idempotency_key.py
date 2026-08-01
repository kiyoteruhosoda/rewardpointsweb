"""クライアントが生成する冪等キー。

モバイルでの二重タップを台帳に二重登録させないための鍵で、台帳ごとに一意
（``UNIQUE (ledger_id, idempotency_key)``）。衝突はエラーにせず、既存の
レコードを返す（ADR-0010）。
"""

from __future__ import annotations

from dataclasses import dataclass

MAX_LENGTH = 64


@dataclass(frozen=True)
class IdempotencyKey:
    value: str

    def __post_init__(self) -> None:
        if not self.value.strip():
            raise ValueError("Idempotency key cannot be empty")
        if len(self.value) > MAX_LENGTH:
            raise ValueError(f"Idempotency key cannot exceed {MAX_LENGTH} characters")


__all__ = ["MAX_LENGTH", "IdempotencyKey"]
