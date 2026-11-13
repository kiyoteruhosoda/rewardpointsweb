"""Check the SSO settings once at startup and log the result.

**The private key is first read only when signing.** Even with wrong permissions, startup and the
settings screen check pass, and it fails only at the moment a user returns from the IdP -- that
pattern is easy to fall into (ADR-0029). Reading it once here makes it noticeable right after deployment.

Setting values themselves are not logged (CLAUDE.md "Logging"). Only "usable / not usable" and,
when not usable, the category are logged.
"""

from __future__ import annotations

import logging

from bounded_contexts.identity_federation.domain.exceptions import (
    SsoNotConfiguredError,
)
from bounded_contexts.identity_federation.infrastructure.client_assertion import (
    read_private_key,
)
from bounded_contexts.identity_federation.presentation.dependencies import (
    identity_provider,
)
from shared.kernel.settings.settings import settings

logger = logging.getLogger(__name__)


def report_sso_configuration() -> None:
    """If SSO is configured to be used, check that it can actually start."""
    if not settings.oidc_enabled:
        return
    provider = identity_provider()
    if provider is None or not provider.is_usable:
        # A mismatch of "meant to enable it but it is disabled" can only be noticed here.
        logger.error("sso_disabled_by_configuration")
        return
    if not provider.credential.uses_private_key:
        logger.info("sso_ready")
        return
    try:
        read_private_key(provider.credential)
    except SsoNotConfiguredError:
        # The reason is already logged by read_private_key (only the exception type).
        logger.error("sso_private_key_unreadable")
        return
    logger.info("sso_ready")


__all__ = ["report_sso_configuration"]
