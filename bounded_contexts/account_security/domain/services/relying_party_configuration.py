"""RP ID とオリジンの整合性（WebAuthn の規則）。

ブラウザは ``navigator.credentials.create()`` の時点で「``rp.id`` が呼び出し元の
実効ドメインと一致するか、その登録可能なサフィックスであること」を確かめ、
外れていれば ``SecurityError`` を投げる。設定が食い違っていても登録の開始まで
は成功してしまうため、サーバー側で先に弾かないと「保存はできたのに、利用者の
画面でだけ失敗する」状態になる。

判定はドメインの規則そのもの（フレームワーク・DB に依らない）なのでここへ置く。
"""

from __future__ import annotations

import ipaddress
import re
from urllib.parse import urlsplit

from bounded_contexts.account_security.domain.exceptions import (
    InvalidWebAuthnOriginError,
    InvalidWebAuthnRelyingPartyIdError,
)

# WebAuthn は安全なコンテキストでしか動かない。http を許すのはブラウザが例外的に
# 安全とみなすループバックだけ（OPERATIONS.md「パスキーを使う前に」参照）。
_HTTP_ALLOWED_HOSTS = frozenset({"localhost"})

# ラベルは英数字とハイフン。国際化ドメインは punycode（``xn--``）へ変換済みの形で持つ。
_LABEL = re.compile(r"^[a-z0-9]([a-z0-9-]*[a-z0-9])?$")


def validate_relying_party_configuration(*, rp_id: str, origin: str) -> None:
    """``rp_id`` が ``origin`` のドメインに対して使えるかを確かめる。

    合わない場合は :class:`InvalidWebAuthnOriginError` か
    :class:`InvalidWebAuthnRelyingPartyIdError` を送出する。
    """
    host = _origin_host(origin)
    identifier = _normalize_domain(rp_id)
    if not _is_domain(identifier):
        raise InvalidWebAuthnRelyingPartyIdError
    if not _is_registrable_suffix(identifier, host):
        raise InvalidWebAuthnRelyingPartyIdError


def _origin_host(origin: str) -> str:
    """オリジンからホスト名を取り出す（``https://example.com:8443`` → ``example.com``）。"""
    parts = urlsplit(origin.strip())
    if parts.scheme not in ("http", "https") or not parts.hostname or parts.path.strip("/"):
        raise InvalidWebAuthnOriginError
    host = _normalize_domain(parts.hostname)
    if parts.scheme == "http" and host not in _HTTP_ALLOWED_HOSTS:
        raise InvalidWebAuthnOriginError
    return host


def _normalize_domain(value: str) -> str:
    """比較用に揃える（前後の空白・大文字・末尾のドットを落とす）。"""
    return value.strip().rstrip(".").lower()


def _is_domain(value: str) -> bool:
    """RP ID として使える形か。IP アドレス・ポート・パス付きは使えない。"""
    if not value or _is_ip_address(value):
        return False
    return all(_LABEL.match(label) for label in value.split("."))


def _is_ip_address(value: str) -> bool:
    try:
        ipaddress.ip_address(value.strip("[]"))
    except ValueError:
        return False
    return True


def _is_registrable_suffix(rp_id: str, host: str) -> bool:
    """``host`` が ``rp_id`` 自身か、その下のドメインか。"""
    return host == rp_id or host.endswith(f".{rp_id}")


__all__ = ["validate_relying_party_configuration"]
