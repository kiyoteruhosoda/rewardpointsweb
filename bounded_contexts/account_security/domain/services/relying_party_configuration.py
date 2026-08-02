"""RP ID とオリジンの整合性（WebAuthn の規則）。

ブラウザは ``navigator.credentials.create()`` の時点で「``rp.id`` が呼び出し元の
実効ドメインと一致するか、その登録可能なサフィックスであること」を確かめ、
外れていれば ``SecurityError`` を投げる。設定が食い違っていても登録の開始まで
は成功してしまうため、サーバー側で先に弾かないと「保存はできたのに、利用者の
画面でだけ失敗する」状態になる。

検証と同時に**正規化した値を返す**。設定に入った空白や既定ポート（``:443``）を
そのまま authenticator へ渡すと、検証は通ったのにブラウザの送るオリジンと
一致しない、という別のずれ方をする。RP を組み立てる側は必ず戻り値を使う。

判定はドメインの規則そのもの（フレームワーク・DB に依らない）なのでここへ置く。
"""

from __future__ import annotations

import ipaddress
import re
from dataclasses import dataclass
from urllib.parse import SplitResult, urlsplit

from bounded_contexts.account_security.domain.exceptions import (
    InvalidWebAuthnOriginError,
    InvalidWebAuthnRelyingPartyIdError,
)

# WebAuthn は安全なコンテキストでしか動かない。http を許すのはブラウザが例外的に
# 安全とみなすループバックだけ（OPERATIONS.md「パスキーを使う前に」参照）。
_HTTP_ALLOWED_HOSTS = frozenset({"localhost"})

# ブラウザの送るオリジンには既定ポートが付かない（``https://example.com:443`` ではなく
# ``https://example.com``）。合わせて落とさないと検証で外れる。
_DEFAULT_PORTS = {"http": 80, "https": 443}

# ラベルは英数字とハイフン。国際化ドメインは punycode（``xn--``）へ変換済みの形で持つ。
_LABEL = re.compile(r"^[a-z0-9]([a-z0-9-]*[a-z0-9])?$")


@dataclass(frozen=True)
class RelyingPartyConfiguration:
    """検証済み・正規化済みの RP 設定。"""

    rp_id: str
    origin: str


def validate_relying_party_configuration(*, rp_id: str, origin: str) -> RelyingPartyConfiguration:
    """``rp_id`` が ``origin`` のドメインに対して使えるかを確かめ、正規化して返す。

    合わない場合は :class:`InvalidWebAuthnOriginError` か
    :class:`InvalidWebAuthnRelyingPartyIdError` を送出する。
    """
    canonical_origin, host = _canonical_origin(origin)
    identifier = _normalize_domain(rp_id)
    if not _is_domain(identifier) or not _is_registrable_suffix(identifier, host):
        raise InvalidWebAuthnRelyingPartyIdError
    return RelyingPartyConfiguration(rp_id=identifier, origin=canonical_origin)


def _canonical_origin(origin: str) -> tuple[str, str]:
    """``scheme://host[:port]`` へ揃えた文字列と、そのホスト名を返す。"""
    parts = urlsplit(origin.strip())
    _reject_non_origin(parts)
    host = _normalize_domain(parts.hostname or "")
    if not host:
        raise InvalidWebAuthnOriginError
    if parts.scheme == "http" and host not in _HTTP_ALLOWED_HOSTS:
        raise InvalidWebAuthnOriginError
    return f"{parts.scheme}://{host}{_explicit_port(parts)}", host


def _reject_non_origin(parts: SplitResult) -> None:
    """オリジンは scheme・ホスト・ポートだけ。それ以外が付いた値は使えない。

    パス・クエリ・フラグメント・認証情報の付いた URL は、ブラウザが
    ``clientDataJSON`` へ入れるオリジンと決して一致しない。ここで弾かないと、
    ブラウザ側の登録は通るのにサーバーの検証だけが落ちる。
    """
    if parts.scheme not in _DEFAULT_PORTS:
        raise InvalidWebAuthnOriginError
    if parts.path.strip("/") or parts.query or parts.fragment or parts.username or parts.password:
        raise InvalidWebAuthnOriginError


def _explicit_port(parts: SplitResult) -> str:
    try:
        port = parts.port
    except ValueError as error:  # ポートが数値でない・範囲外
        raise InvalidWebAuthnOriginError from error
    return "" if port is None or port == _DEFAULT_PORTS[parts.scheme] else f":{port}"


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
    """``host`` が ``rp_id`` 自身か、その下のドメインか。

    RP ID に使えるのは**登録できる**ドメインだけ。``example.com`` に対する ``com``
    のような公開サフィックスはブラウザが拒む。ここではラベルが 1 つだけの RP ID を
    落として、その大半（``com`` / ``jp`` 等）を弾く。``localhost`` のようにホスト
    そのものが 1 ラベルの場合は一致とみなす。

    ``co.uk`` のような多段の公開サフィックスまでは判定しない（公開サフィックス
    リストが要る）。この設定を選ぶのは現実的でなく、外した場合もブラウザ側で
    拒まれるだけなので、リストを抱える代わりに割り切る。
    """
    if host == rp_id:
        return True
    if "." not in rp_id:
        return False
    return host.endswith(f".{rp_id}")


__all__ = ["RelyingPartyConfiguration", "validate_relying_party_configuration"]
