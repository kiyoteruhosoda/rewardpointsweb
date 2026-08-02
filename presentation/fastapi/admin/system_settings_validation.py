"""保存しようとしている設定の突き合わせ検証。

単独の項目の型（整数か・真偽値か）は Pydantic とフォームが見る。ここで見るのは
**複数のキーが噛み合っているか**——片方だけを見ても正しさが決まらないもの。

誤った組み合わせを保存できてしまうと、壊れるのは設定画面ではなく利用者の画面
になる（例: RP ID とオリジンが食い違うと、パスキーの登録がブラウザ側で拒まれる）。
保存の時点で弾き、直すべきキーが分かるエラーコードを返す。
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from bounded_contexts.account_security.domain.services.relying_party_configuration import (
    validate_relying_party_configuration,
)


def validate_system_settings(effective: Mapping[str, Any]) -> None:
    """*effective*（保存後に有効となる値）の組み合わせを確かめる。

    合わない場合は該当コンテキストのドメイン例外を送出する。
    """
    validate_relying_party_configuration(
        rp_id=_as_text(effective.get("WEBAUTHN_RP_ID")),
        origin=_as_text(effective.get("WEBAUTHN_ORIGIN")),
    )


def _as_text(value: Any) -> str:
    return "" if value is None else str(value)


__all__ = ["validate_system_settings"]
