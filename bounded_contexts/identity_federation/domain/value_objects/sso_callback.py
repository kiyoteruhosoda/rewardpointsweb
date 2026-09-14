"""IdP からの戻り（``code`` / ``state`` と、ブラウザが持っている合言葉）。

ログインの完了と連携の完了（ADR-0036）で同じ 3 つを受け取るので、値としてまとめる。
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class SsoCallback:
    code: str
    state: str
    #: 送り出したときに Cookie へ置いた合言葉。無ければ照合に落ちる。
    browser_binding: str | None


__all__ = ["SsoCallback"]
