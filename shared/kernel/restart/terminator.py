"""How a process that received a restart request terminates.

The container runs with ``restart: unless-stopped``, so "restart the app"
simply means "shut the main process down cleanly". After it exits Docker starts the
container again and the entrypoint runs as usual, starting from migrations.

Which process to terminate depends on the process layout:

- Gunicorn (production): terminate the arbiter (parent), not the workers. Killing only
  workers makes the arbiter recreate them in the same environment, so the container does not restart.
- Standalone Uvicorn (development): the main process itself, where the watcher thread runs.
"""

from __future__ import annotations

import logging
import os
import signal
from typing import Protocol

logger = logging.getLogger(__name__)


class ProcessTerminator(Protocol):
    """Send a termination signal to a process for a restart."""

    def terminate(self, reason: str) -> None:
        """Start a graceful shutdown."""


class SelfProcessTerminator:
    """Send SIGTERM to the own process (standalone Uvicorn, worker process)."""

    def terminate(self, reason: str) -> None:
        pid = os.getpid()
        logger.warning(
            "Terminating own process on restart request: pid=%s reason=%s",
            pid,
            reason,
            extra={"event": "restart.terminate.self"},
        )
        os.kill(pid, signal.SIGTERM)


class SupervisorProcessTerminator:
    """Send SIGTERM to the parent process (Gunicorn arbiter)."""

    def terminate(self, reason: str) -> None:
        pid = os.getppid()
        logger.warning(
            "Terminating parent process on restart request: ppid=%s reason=%s",
            pid,
            reason,
            extra={"event": "restart.terminate.supervisor"},
        )
        os.kill(pid, signal.SIGTERM)


def build_process_terminator() -> ProcessTerminator:
    """Choose the termination method that fits the running process layout.

    Gunicorn sets ``SERVER_SOFTWARE`` in the arbiter and workers inherit it.
    Only when this environment variable is present is the parent (arbiter) terminated.
    """
    if os.environ.get("SERVER_SOFTWARE", "").lower().startswith("gunicorn"):
        return SupervisorProcessTerminator()
    return SelfProcessTerminator()


__all__ = [
    "ProcessTerminator",
    "SelfProcessTerminator",
    "SupervisorProcessTerminator",
    "build_process_terminator",
]
