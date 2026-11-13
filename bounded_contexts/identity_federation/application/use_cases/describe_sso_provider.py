"""Answer whether to show a "Sign in with SSO" button on the login screen.

Since it is called unauthenticated, **it does not return the connection URL or client ID**. It returns only
"whether it is usable" and "the name to show on the button".
"""

from __future__ import annotations

from dataclasses import dataclass

from bounded_contexts.identity_federation.application.dto.sso_dto import SsoProviderDto
from bounded_contexts.identity_federation.domain.value_objects.identity_provider import (
    IdentityProvider,
)


@dataclass(frozen=True)
class DescribeSsoProvider:
    provider: IdentityProvider | None

    def execute(self) -> SsoProviderDto:
        usable = self.provider is not None and self.provider.is_usable
        return SsoProviderDto(
            enabled=usable,
            display_name=self.provider.display_name if usable and self.provider else "",
        )


__all__ = ["DescribeSsoProvider"]
