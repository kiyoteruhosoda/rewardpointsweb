"""Application self-restart.

A mechanism that lets an admin tell the app itself to restart, so that settings saved in
the admin screen that are **read only at startup** (log settings, CORS allowed origins, etc.)
take effect.

The request is stored in the DB (``app.restart_request`` in ``system_settings``) and each process
picks it up with :class:`RestartWatcher` and terminates itself. The container is
started again automatically by ``restart: unless-stopped``.

Callers use only the public names of this module::

    # Request (admin API)
    RestartRequestStore().save(db, [RestartScope.WEB], requested_by="user:1")

    # Receive (process startup)
    start_restart_watcher(RestartScope.WEB)
"""

from __future__ import annotations

import logging

from shared.kernel.restart.request import (
    RESTART_REQUEST_SETTING_KEY,
    RestartRequest,
    RestartRequestReader,
    RestartRequestStore,
)
from shared.kernel.restart.scope import ALL_RESTART_SCOPES, RestartScope
from shared.kernel.restart.terminator import (
    ProcessTerminator,
    SelfProcessTerminator,
    SupervisorProcessTerminator,
    build_process_terminator,
)
from shared.kernel.restart.watcher import (
    DEFAULT_POLL_INTERVAL_SECONDS,
    RestartWatcher,
)

logger = logging.getLogger(__name__)

_watchers: dict[RestartScope, RestartWatcher] = {}


def start_restart_watcher(scope: RestartScope) -> RestartWatcher | None:
    """Start watching restart requests addressed to *scope*.

    Does nothing under tests (``TESTING``). When called twice for the same scope, returns
    the first watcher as is (one is expected per Gunicorn worker, so it must not be
    duplicated within a process).
    """
    from shared.kernel.settings.settings import settings

    if settings.testing:
        return None

    existing = _watchers.get(scope)
    if existing is not None:
        return existing

    watcher = RestartWatcher(scope)
    try:
        watcher.start()
    except Exception:
        # A watcher failing to start must not stop the app from starting
        logger.warning(
            "Could not start watching restart requests: scope=%s",
            scope.value,
            exc_info=True,
        )
        return None

    _watchers[scope] = watcher
    return watcher


def stop_restart_watchers() -> None:
    """Stop the started watcher thread (for process exit and test cleanup)."""
    for watcher in _watchers.values():
        watcher.stop()
    _watchers.clear()


__all__ = [
    "ALL_RESTART_SCOPES",
    "DEFAULT_POLL_INTERVAL_SECONDS",
    "RESTART_REQUEST_SETTING_KEY",
    "ProcessTerminator",
    "RestartRequest",
    "RestartRequestReader",
    "RestartRequestStore",
    "RestartScope",
    "RestartWatcher",
    "SelfProcessTerminator",
    "SupervisorProcessTerminator",
    "build_process_terminator",
    "start_restart_watcher",
    "stop_restart_watchers",
]
