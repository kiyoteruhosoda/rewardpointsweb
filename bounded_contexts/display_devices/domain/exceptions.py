"""表示端末（display_devices）のドメイン例外。

``code`` は API がそのまま返すエラーコード（表示文言はフロントエンドが決める）。
受け取りの口（``/api/display/pairings/claim``）の 2 つは RFC 8628 の綴りに合わせる。
"""

from __future__ import annotations


class DisplayDevicesError(Exception):
    code = "display_devices_error"


class PairingNotFoundError(DisplayDevicesError):
    """その確認コードのペアリングが無い（打ち間違い・承認済み）。"""

    code = "pairing_not_found"


class PairingExpiredError(DisplayDevicesError):
    """確認コードの有効期限（10 分）が過ぎた。端末は新しいコードを出し直している。"""

    code = "pairing_expired"


class AuthorizationPendingError(DisplayDevicesError):
    """まだ承認されていない。端末は間隔を空けて問い合わせ続ける（RFC 8628）。"""

    code = "authorization_pending"


class ExpiredTokenError(DisplayDevicesError):
    """期限切れ・受け取り済み・知らない端末の秘密。端末はペアリングをやり直す（RFC 8628）。

    3 つを分けないのは、知らない秘密を持ってきた相手に「その秘密は実在した」と
    教えないため。端末の側の打つ手はどれも同じ（やり直す）。
    """

    code = "expired_token"


class InvalidDeviceCredentialError(DisplayDevicesError):
    """端末の資格情報が無い・知らない（外された）。端末はペアリングの画面へ戻る。"""

    code = "invalid_device_credential"


class DeviceCredentialExpiredError(DisplayDevicesError):
    """使われないまま失効した（90 日）。その表示端末は外す。"""

    code = "device_credential_expired"

    def __init__(self, account_id: int) -> None:
        super().__init__(self.code)
        self.account_id = account_id


__all__ = [
    "AuthorizationPendingError",
    "DeviceCredentialExpiredError",
    "DisplayDevicesError",
    "ExpiredTokenError",
    "InvalidDeviceCredentialError",
    "PairingExpiredError",
    "PairingNotFoundError",
]
