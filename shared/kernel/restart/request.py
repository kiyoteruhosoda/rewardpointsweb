"""Persistence of restart requests.

With the ``app.restart_request`` record of the ``system_settings`` table as the single
source, it holds "when, who, and which service's restart was requested".

The admin API process cannot send a signal directly to the process that should restart
(Gunicorn runs several workers, and splitting services later would mean separate containers). The
request is put in the DB, each process picks it up with :mod:`shared.kernel.restart.watcher`, terminates
itself, and comes back through Docker's restart policy. This way the docker socket
need not be mounted into the container.

Requests are kept **independently per scope**. With a single overwritten request, two requests
arriving within the watcher's polling interval (default 10 seconds) would overwrite the first
before it is read, and a process that had not read it yet would miss its own restart.
"""

from __future__ import annotations

import logging
from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any, Protocol

from sqlalchemy.orm import Session

from shared.kernel.restart.scope import ALL_RESTART_SCOPES, RestartScope

logger = logging.getLogger(__name__)

RESTART_REQUEST_SETTING_KEY = "app.restart_request"


@dataclass(frozen=True)
class RestartRequest:
    """The latest restart request for a scope.

    ``token`` is a string identifying the request (ISO form of the request time). The watcher
    uses the token read at startup as the baseline and restarts only when the value **changes**.
    Because it checks for change rather than comparing times, it does not fall into a restart
    loop even if the app container's and the DB's clocks drift.
    """

    scope: RestartScope
    token: str
    requested_at: datetime | None
    requested_by: str | None
    reason: str | None

    def to_payload(self) -> dict[str, Any]:
        return {
            "token": self.token,
            "requested_at": self.requested_at.isoformat() if self.requested_at else None,
            "requested_by": self.requested_by,
            "reason": self.reason,
        }

    @classmethod
    def from_payload(cls, scope: RestartScope, payload: Any) -> RestartRequest | None:
        if not isinstance(payload, dict):
            return None
        token = payload.get("token")
        if not isinstance(token, str) or not token:
            return None
        requested_by = payload.get("requested_by")
        reason = payload.get("reason")
        return cls(
            scope=scope,
            token=token,
            requested_at=_parse_timestamp(payload.get("requested_at")),
            requested_by=requested_by if isinstance(requested_by, str) else None,
            reason=reason if isinstance(reason, str) else None,
        )


def _parse_timestamp(value: Any) -> datetime | None:
    if not isinstance(value, str) or not value:
        return None
    try:
        parsed = datetime.fromisoformat(value)
    except ValueError:
        return None
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=UTC)
    return parsed.astimezone(UTC)


def _decode_requests(payload: Any) -> dict[RestartScope, RestartRequest]:
    """Parse the stored format ``{"scopes": {"web": {...}}}``."""
    if not isinstance(payload, dict):
        return {}
    raw_scopes = payload.get("scopes")
    if not isinstance(raw_scopes, dict):
        return {}

    requests: dict[RestartScope, RestartRequest] = {}
    for raw_scope, raw_request in raw_scopes.items():
        scope = RestartScope.parse(raw_scope)
        if scope is None:
            continue
        request = RestartRequest.from_payload(scope, raw_request)
        if request is not None:
            requests[scope] = request
    return requests


def _encode_requests(requests: Mapping[RestartScope, RestartRequest]) -> dict[str, Any]:
    return {"scopes": {scope.value: requests[scope].to_payload() for scope in ALL_RESTART_SCOPES if scope in requests}}


class RestartRequestReader(Protocol):
    """Reads one restart request addressed to a scope.

    :class:`~shared.kernel.restart.watcher.RestartWatcher` depends only on this interface
    (DIP), so a test double without a DB can be substituted.
    """

    def load(self, scope: RestartScope) -> RestartRequest | None:
        """Return the latest request addressed to *scope*, or ``None``."""


class RestartRequestStore:
    """Reads and writes the ``app.restart_request`` record."""

    def load_all(self) -> dict[RestartScope, RestartRequest]:
        """Return the latest request per scope. Empty when the DB is unavailable."""
        from shared.kernel.settings.system_setting_records import (
            SystemSettingRecordReader,
        )

        try:
            payload = SystemSettingRecordReader.read_json(RESTART_REQUEST_SETTING_KEY)
        except Exception:
            logger.debug("Failed to read restart requests", exc_info=True)
            return {}
        return _decode_requests(payload)

    def load(self, scope: RestartScope) -> RestartRequest | None:
        """Return the latest request addressed to *scope*."""
        return self.load_all().get(scope)

    def save(
        self,
        session: Session,
        scopes: Iterable[RestartScope],
        *,
        requested_by: str | None = None,
        reason: str | None = None,
        requested_at: datetime | None = None,
    ) -> tuple[RestartRequest, ...]:
        """Save a restart request (called from within a request).

        An empty target means all scopes. Only the given scopes are rewritten;
        requests left for other scopes are kept (so requests not yet picked up
        are not erased).
        """
        from shared.infrastructure.models import SystemSetting

        targets = tuple(scope for scope in ALL_RESTART_SCOPES if scope in set(scopes))
        if not targets:
            targets = ALL_RESTART_SCOPES

        moment = requested_at or datetime.now(UTC)
        token = moment.isoformat()

        record = session.get(SystemSetting, RESTART_REQUEST_SETTING_KEY)
        requests = _decode_requests(record.setting_json if record is not None else None)
        for scope in targets:
            requests[scope] = RestartRequest(
                scope=scope,
                token=token,
                requested_at=moment,
                requested_by=requested_by,
                reason=reason,
            )

        payload = _encode_requests(requests)
        if record is None:
            session.add(SystemSetting(setting_key=RESTART_REQUEST_SETTING_KEY, setting_json=payload))
        else:
            record.setting_json = payload
        session.flush()

        logger.info(
            "Saved restart request: scopes=%s requested_by=%s",
            ",".join(scope.value for scope in targets),
            requested_by or "-",
            extra={"event": "restart.requested"},
        )
        return tuple(requests[scope] for scope in targets)


__all__ = [
    "RESTART_REQUEST_SETTING_KEY",
    "RestartRequest",
    "RestartRequestReader",
    "RestartRequestStore",
]
