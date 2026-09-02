"""連携先の設定が「使える」と言えるかの判断。"""

from __future__ import annotations

from dataclasses import replace

import pytest

from bounded_contexts.identity_federation.domain.exceptions import (
    SsoNotConfiguredError,
)
from bounded_contexts.identity_federation.domain.value_objects.client_credential import (
    CLIENT_SECRET_BASIC,
    PRIVATE_KEY_JWT,
    ClientCredential,
)
from bounded_contexts.identity_federation.domain.value_objects.identity_provider import (
    IdentityProvider,
    require_usable,
)


def _provider(
    credential: ClientCredential,
    *,
    issuer: str = "https://idp.example",
    client_id: str = "rewardpointsweb",
    redirect_uri: str = "https://app.example/api/auth/sso/callback",
) -> IdentityProvider:
    return IdentityProvider(
        display_name="idp",
        issuer=issuer,
        client_id=client_id,
        credential=credential,
        redirect_uri=redirect_uri,
    )


def test_secret_and_private_key_are_judged_separately() -> None:
    with_secret = ClientCredential(method=CLIENT_SECRET_BASIC, secret="s")
    with_key = ClientCredential(method=PRIVATE_KEY_JWT, private_key_file="/srv/secrets/oidc/client.key")

    assert _provider(with_secret).is_usable is True
    assert _provider(with_key).is_usable is True
    # 材料が方式と噛み合っていない
    assert _provider(ClientCredential(method=PRIVATE_KEY_JWT, secret="s")).is_usable is False
    assert _provider(ClientCredential(method=CLIENT_SECRET_BASIC, private_key_file="/k")).is_usable is False


def test_an_unknown_method_is_a_gap_not_a_default() -> None:
    """綴り違いを既定の方式へ落とすと、IdP からは ``invalid_client`` しか返らない。"""
    assert ClientCredential(method="private-key-jwt", private_key_file="/k").is_complete is False


@pytest.mark.parametrize("missing", ["issuer", "client_id", "redirect_uri"])
def test_every_connection_detail_is_required(missing: str) -> None:
    provider = _provider(ClientCredential(method=CLIENT_SECRET_BASIC, secret="s"), **{missing: ""})

    assert provider.is_usable is False


def test_openid_scope_is_always_requested_first_and_duplicates_are_folded() -> None:
    provider = _provider(ClientCredential(method=CLIENT_SECRET_BASIC, secret="s"))
    with_scopes = replace(provider, scopes=("email", "openid", "email"))

    assert with_scopes.scope_parameter == "openid email"


def test_require_usable_rejects_a_provider_that_cannot_start() -> None:
    with pytest.raises(SsoNotConfiguredError):
        require_usable(None)
    with pytest.raises(SsoNotConfiguredError):
        require_usable(_provider(ClientCredential(method=CLIENT_SECRET_BASIC)))
