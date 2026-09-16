"""IdP が名乗った利用者（クレームを対応付けた結果）。

``subject`` は IdP の中で不変の識別子で、アカウントの結び付きはこれで持つ。
メールアドレスは変わり得るため、結び付きの**鍵にはしない**（初回に既存の利用者を
見つける手掛かりとしてだけ使う。ADR-0029）。

⚠ **鍵ではない以上、無くても成立する**（ADR-0038）。IdP によっては出てこない
——**そのときに弾いていたのは、鍵にしていた名残である。**
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class FederatedUser:
    subject: str
    #: ⚠ **任意である**（ADR-0038）。結び付きの鍵は ``subject`` なので、既に
    #: 結び付いている相手はメールアドレスが無くても入れる。無いと困るのは
    #: **初回に既存の利用者を探すとき**だけである。
    email: str | None
    display_name: str
    email_verified: bool = False
    #: IdP でのログイン識別子（``preferred_username``）。初めての相手の口座を作るとき、
    #: このアプリの ``username`` の元にする（ADR-0041）。⚠ **任意である** ——IdP が
    #: 出さない（``profile`` scope を求めていない）こともあり、そのときは作れない。
    preferred_username: str | None = None

    @property
    def email_domain(self) -> str:
        _, _, domain = (self.email or "").rpartition("@")
        return domain.lower()


__all__ = ["FederatedUser"]
