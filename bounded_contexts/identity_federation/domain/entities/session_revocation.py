"""A record saying "this session may no longer be used" (ADR-0032).

Sessions in this template are **JWTs with no server-side record**, so there is no place to apply
a received revocation immediately. Instead, "when it was stopped" is kept as a row, and
**tokens issued before that time are treated as invalid**.

``expires_at`` exists only for cleanup. Past the refresh token lifetime, tokens issued
before that time expire on their own, so keeping the row is pointless.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from datetime import datetime, timedelta

from bounded_contexts.identity_federation.domain.entities.federated_identity import (
    FederatedIdentity,
)
from bounded_contexts.identity_federation.domain.value_objects.federated_login import (
    FederatedLogin,
)
from bounded_contexts.identity_federation.domain.value_objects.federated_session import (
    FederatedSession,
)
from bounded_contexts.identity_federation.domain.value_objects.logout_notice import (
    LogoutNotice,
)


@dataclass(frozen=True)
class SessionRevocation:
    jti: str
    session: FederatedSession
    revoked_at: datetime
    expires_at: datetime

    @classmethod
    def of(cls, notice: LogoutNotice, *, now: datetime, keep_for_seconds: int) -> SessionRevocation:
        """Turn a notice into a record.

        ``revoked_at`` is **the time it was received**, not the ``iat`` of the ``logout_token``.
        This keeps an old re-sent notice from taking down sessions alive now
        (re-sends themselves are rejected by ``jti``, but the source of the time is kept separate).
        """
        return cls(
            jti=notice.jti,
            session=notice.session,
            revoked_at=now,
            expires_at=now + timedelta(seconds=keep_for_seconds),
        )

    @classmethod
    def after_reconciliation(
        cls,
        identity: FederatedIdentity,
        *,
        now: datetime,
        keep_for_seconds: int,
    ) -> SessionRevocation:
        """Stop **all** SSO sessions of a person whom assay said "can no longer use" in periodic reconciliation (ADR-0040).

        ⚠ **Derive ``jti`` from ``(issuer, sub, time of the last SSO sign-in)``.**

        - For the same login, even running hourly once per worker, **one row** is enough
          (the second is rejected by :meth:`SessionRevocationRepository.record` as a duplicate ``jti``)
        - When the user comes back in assay, signs in again and is stopped again, the time changes, so it is **a new row**.
          ⚠ If ``jti`` stayed the same, the old row would remain, the new one would not be written, and the
          re-signed-in session would be missed (a record only applies to "what started before that time")

        The ``jti`` column is 64 characters, so the inputs are hashed to fit. It is kept in a separate space from
        IdP-issued ``jti`` values by mixing a prefix into the inputs.
        """
        generation = identity.last_login_at or identity.linked_at
        material = "|".join(
            ("sso-reconciliation", identity.issuer, identity.subject, generation.isoformat() if generation else "")
        )
        return cls(
            jti=hashlib.sha256(material.encode("utf-8")).hexdigest(),
            session=FederatedSession(issuer=identity.issuer, subject=identity.subject, session_id=None),
            revoked_at=now,
            expires_at=now + timedelta(seconds=keep_for_seconds),
        )

    def covers(self, login: FederatedLogin) -> bool:
        """このログインを、この記録が無効にするか。

        ``session_id`` が ``None`` の記録は**その利用者のすべてのセッション**に効く。
        比べるのは**セッションが始まった時刻**で、止めたあとに入り直した利用者は
        巻き添えにしない。
        """
        target = login.session
        if (self.session.issuer, self.session.subject) != (target.issuer, target.subject):
            return False
        if self.session.session_id is not None and self.session.session_id != target.session_id:
            return False
        return login.started_at <= self.revoked_at


__all__ = ["SessionRevocation"]
