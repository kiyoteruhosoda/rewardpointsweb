"""認可要求の控え（ブラウザを IdP へ送り出してから戻るまで）。

``state`` は「戻ってきた応答が自分の出した要求か」を確かめるための値、``nonce``
は「受け取った ID トークンが自分の要求に対する応答か」を確かめるための値、
``code_verifier`` は PKCE（横取りした認可コードを使わせないための証拠）。
どれも出した側が覚えていなければ確かめられない。

``binding_hash`` は「**この要求を出したブラウザ**が戻ってきたか」を確かめるための値。
控えは全員で 1 つの表を共有するので、``state`` を知っているだけの相手でも戻りを
完了できてしまう。攻撃者が自分で始めた認可要求の URL を被害者に踏ませると、被害者は
**攻撃者として**ログインした状態になる（ログイン CSRF）。送り出すときに Cookie へ
置いた合言葉と突き合わせて、それを止める。合言葉そのものは保存しない。

Gunicorn は複数ワーカーで動き、送り出したプロセスと戻り先のプロセスは一致しない。
プロセスのメモリではなく DB へ置く（パスキーのチャレンジと同じ理由）。
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime


@dataclass(frozen=True)
class SsoLoginSession:
    state: str
    nonce: str
    code_verifier: str
    redirect_to: str
    expires_at: datetime
    binding_hash: str = ""

    def is_expired(self, now: datetime) -> bool:
        return now >= self.expires_at

    def belongs_to(self, binding_hash: str) -> bool:
        """送り出したブラウザが持っている合言葉か。

        突き合わせはハッシュ同士で行う（生の値は保存していない）。
        """
        return bool(binding_hash) and binding_hash == self.binding_hash


__all__ = ["SsoLoginSession"]
