"""パスワードの長さの決まり。

上限は、ログインなしで届く口（ログイン・再設定）に大きな文字列を送らせて
ハッシュの計算をさせないため（task #733）。128 字はパスフレーズにも足りる。
"""

from __future__ import annotations

MIN_LENGTH = 8
MAX_LENGTH = 128

__all__ = ["MAX_LENGTH", "MIN_LENGTH"]
