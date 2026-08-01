"""ログイン識別子（``users.username``）。

メールアドレスから識別子を分離したことで、識別子は「アプリが決める文字列」に
なった（ADR-0011）。既存アカウントの移行値はメールアドレスなので、``@`` と
``.`` を含む値も受け付ける必要がある。

大文字・小文字は区別しない。区別すると ``Taro`` と ``taro`` が別アカウントとして
並び、家庭内での取り違えを招く。正規化（小文字化）はここで 1 度だけ行い、
保存・検索の双方がこの値を使う。
"""

from __future__ import annotations

import re
from dataclasses import dataclass

MIN_LENGTH = 3
MAX_LENGTH = 255

# 子どもが手で入力することを踏まえ、空白と紛らわしい記号を許さない。
_ALLOWED = re.compile(r"^[a-z0-9._@+-]+$")


@dataclass(frozen=True)
class Username:
    value: str

    def __post_init__(self) -> None:
        normalized = self.value.strip().lower()
        object.__setattr__(self, "value", normalized)
        if len(normalized) < MIN_LENGTH:
            raise ValueError(f"Username must be at least {MIN_LENGTH} characters")
        if len(normalized) > MAX_LENGTH:
            raise ValueError(f"Username cannot exceed {MAX_LENGTH} characters")
        if not _ALLOWED.match(normalized):
            raise ValueError("Username may only contain letters, digits and . _ - + @")


def normalize_username(value: str) -> str:
    """検索のために同じ正規化を通す（不正な値はここで弾かれる）。"""
    return Username(value).value


__all__ = ["MAX_LENGTH", "MIN_LENGTH", "Username", "normalize_username"]
