"""家族のルール（家族で決めた約束ごとのメモ）。

「テストで 90 点なら 100 pt」「ゲームは 1 時間で 50 pt」といった、その家族の
決めごとを人の言葉のまま持つ。機械は解釈しない — 付与そのものは親が手で記録するか
毎日のボーナス（ADR-0024）が受け持ち、ここは **何を約束したか** を家族の全員が
同じ文面で読めるようにするためだけにある。

決めごとが無い状態は「空の文字列」ではなく **設定なし**（``None``）で表す。この
値オブジェクトが存在するときは必ず中身がある。
"""

from __future__ import annotations

from dataclasses import dataclass

#: 画面で読み切れる長さの上限。箇条書きで 20〜30 行ほど入る
MAX_LENGTH = 2000


@dataclass(frozen=True)
class FamilyRules:
    value: str

    def __post_init__(self) -> None:
        if not self.value.strip():
            raise ValueError("Family rules cannot be empty")
        if len(self.value) > MAX_LENGTH:
            raise ValueError(f"Family rules cannot exceed {MAX_LENGTH} characters")


__all__ = ["MAX_LENGTH", "FamilyRules"]
