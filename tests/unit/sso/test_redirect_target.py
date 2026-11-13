"""Where to return after sign-in (never to an external URL)."""

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
        # Scheme-relative. The browser opens it as an external site
        "//phishing.example",
        # Some browsers treat it as /
        "/\\phishing.example",
        "javascript:alert(1)",
    ],
)
def test_falls_back_to_the_entrance_for_anything_else(value: str | None) -> None:
    assert RedirectTarget.parse(value).path == DEFAULT_TARGET
