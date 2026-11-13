"""Cross-checks on settings about to be saved.

The type of a single item (integer, boolean) is checked by Pydantic and the form. This checks
**whether several keys fit together**: things whose correctness cannot be judged from one key alone.

If a wrong combination can be saved, what breaks is not the settings screen but the user's screen
(e.g. if the RP ID and the origin disagree, the browser rejects passkey registration).
Reject it at save time and return an error code that tells which key to fix.
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from bounded_contexts.account_security.domain.services.relying_party_configuration import (
    validate_relying_party_configuration,
)


def validate_system_settings(effective: Mapping[str, Any]) -> None:
    """Check the combination of *effective* values (the values in effect after saving).

    Raise the relevant context's domain exception if they do not fit.
    """
    validate_relying_party_configuration(
        rp_id=_as_text(effective.get("WEBAUTHN_RP_ID")),
        origin=_as_text(effective.get("WEBAUTHN_ORIGIN")),
    )


def _as_text(value: Any) -> str:
    return "" if value is None else str(value)


__all__ = ["validate_system_settings"]
