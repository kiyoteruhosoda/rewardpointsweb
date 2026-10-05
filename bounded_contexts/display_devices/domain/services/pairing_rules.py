"""ペアリングと端末の資格情報の時間の決まり（ADR-0047）。

設定にしないのは、どれも「表示端末の作り」の一部で、運用で回す値ではないため。
"""

from __future__ import annotations

from datetime import timedelta

#: 確認コードの有効期限。端末は切れたら新しいコードを出し直す
PAIRING_TTL = timedelta(minutes=10)
#: 端末が受け取りを問い合わせる間隔（RFC 8628 の ``interval``）
POLL_INTERVAL_SECONDS = 5
#: 期限が切れたペアリングを、この長さを過ぎたら消す（溜めない）
PAIRING_RETENTION = timedelta(days=1)
#: 使われないまま、この長さを過ぎた資格情報は失効させる。つけっぱなしなら 5 分ごとに使われる
CREDENTIAL_IDLE_LIMIT = timedelta(days=90)


__all__ = ["CREDENTIAL_IDLE_LIMIT", "PAIRING_RETENTION", "PAIRING_TTL", "POLL_INTERVAL_SECONDS"]
