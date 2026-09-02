"""ログイン後の戻り先（外部の URL へ出さない）。"""

from __future__ import annotations

import pytest

from bounded_contexts.identity_federation.domain.value_objects.redirect_target import (
    DEFAULT_TARGET,
    RedirectTarget,
)


@pytest.mark.parametrize("value", ["/", "/families/1", "/families/1/ledgers/2?tab=history"])
def test_keeps_paths_inside_the_application(value: str) -> None:
    assert RedirectTarget.parse(value).path == value


@pytest.mark.parametrize(
    "value",
    [
        None,
        "",
        "   ",
        "https://phishing.example",
        # スキーム相対。ブラウザは外部サイトとして開く
        "//phishing.example",
        # 一部のブラウザが / として扱う
        "/\\phishing.example",
        "javascript:alert(1)",
    ],
)
def test_falls_back_to_the_entrance_for_anything_else(value: str | None) -> None:
    assert RedirectTarget.parse(value).path == DEFAULT_TARGET
