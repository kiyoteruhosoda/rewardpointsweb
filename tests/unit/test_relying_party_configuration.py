"""RP ID とオリジンの整合性（WebAuthn の規則）の検証。"""

from __future__ import annotations

import pytest

from bounded_contexts.account_security.domain.exceptions import (
    InvalidWebAuthnOriginError,
    InvalidWebAuthnRelyingPartyIdError,
)
from bounded_contexts.account_security.domain.services.relying_party_configuration import (
    validate_relying_party_configuration,
)


@pytest.mark.parametrize(
    ("rp_id", "origin"),
    [
        # 既定（開発）
        ("localhost", "http://localhost:5173"),
        ("localhost", "http://localhost:8080"),
        # 本番
        ("rewardpointsweb.com", "https://rewardpointsweb.com"),
        ("rewardpointsweb.com", "https://rewardpointsweb.com:8443"),
        # サブドメインで開き、親ドメインを RP ID にする（登録可能なサフィックス）
        ("rewardpointsweb.com", "https://app.rewardpointsweb.com"),
        ("example.co.jp", "https://www.example.co.jp"),
        # 大文字・末尾のドット・前後の空白は揃えて比較する
        ("Example.COM", " https://EXAMPLE.com. "),
    ],
)
def test_accepts_matching_configuration(rp_id: str, origin: str) -> None:
    validate_relying_party_configuration(rp_id=rp_id, origin=origin)


@pytest.mark.parametrize(
    ("rp_id", "origin", "expected"),
    [
        # 設定に紛れた空白・大文字はここで落とす。そのまま authenticator へ渡すと
        # ブラウザ側の rp.id 照合とオリジンの比較が外れる。
        (" Example.COM ", " HTTPS://Example.com ", ("example.com", "https://example.com")),
        # 末尾のドット・スラッシュ
        ("example.com.", "https://example.com./", ("example.com", "https://example.com")),
        # 既定ポートはブラウザの送るオリジンに付かない
        ("example.com", "https://example.com:443", ("example.com", "https://example.com")),
        ("localhost", "http://localhost:80", ("localhost", "http://localhost")),
        # 既定以外のポートは残す
        ("example.com", "https://example.com:8443", ("example.com", "https://example.com:8443")),
    ],
)
def test_returns_normalized_values(rp_id: str, origin: str, expected: tuple[str, str]) -> None:
    configuration = validate_relying_party_configuration(rp_id=rp_id, origin=origin)
    assert (configuration.rp_id, configuration.origin) == expected


@pytest.mark.parametrize(
    ("rp_id", "origin"),
    [
        # 画面から報告された誤り: RP 名をそのまま RP ID に入れてしまった
        ("rewardpointsweb", "https://rewardpointsweb.com"),
        # 別のドメイン
        ("example.com", "https://rewardpointsweb.com"),
        # 部分一致はサフィックスではない（ドット区切りで見る）
        ("pointsweb.com", "https://rewardpointsweb.com"),
        # 逆向き（子ドメインを RP ID にして親で開く）は使えない
        ("app.example.com", "https://example.com"),
        # 公開サフィックス（登録できるドメインではない）
        ("com", "https://example.com"),
        ("jp", "https://www.example.jp"),
        # RP ID にドメイン名以外は書けない
        ("", "https://example.com"),
        ("192.0.2.10", "https://192.0.2.10"),
        ("example.com:8443", "https://example.com:8443"),
        ("https://example.com", "https://example.com"),
        ("example.com/path", "https://example.com"),
    ],
)
def test_rejects_mismatched_relying_party_id(rp_id: str, origin: str) -> None:
    with pytest.raises(InvalidWebAuthnRelyingPartyIdError) as error:
        validate_relying_party_configuration(rp_id=rp_id, origin=origin)
    assert error.value.code == "invalid_webauthn_rp_id"


@pytest.mark.parametrize(
    "origin",
    [
        "",
        "example.com",  # scheme が無い
        "ftp://example.com",
        "https://",
        "https://example.com/app",  # パス付きはオリジンではない
        "http://example.com",  # http はループバックだけ（WebAuthn は安全なコンテキスト必須）
        # 以下はブラウザが clientDataJSON へ入れるオリジンと一致し得ない。通すと
        # 「登録はできたのにサーバーの検証だけ落ちる」形で失敗する。
        "https://example.com?tenant=1",
        "https://example.com#top",
        "https://user:pass@example.com",
        "https://example.com:port",
        "https://example.com:99999",
    ],
)
def test_rejects_unusable_origin(origin: str) -> None:
    with pytest.raises(InvalidWebAuthnOriginError) as error:
        validate_relying_party_configuration(rp_id="example.com", origin=origin)
    assert error.value.code == "invalid_webauthn_origin"
