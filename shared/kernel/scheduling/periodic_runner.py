"""Background thread that runs a job at a fixed interval.

The entry point for work no request triggers, such as noticing the date changed and
granting points (ADR-0024). The minimal mechanism that avoids adding another container
with a clock or an external cron, shaped the same as ``RestartWatcher``.

It keeps two promises.

- **It does not stop.** The thread survives a round that ends in an exception (if a transient
  DB failure stopped grants forever, days would pass without anyone noticing).
- **It runs a round right away.** It runs once right after startup, then waits the interval.
  Anything missed while it was stopped is caught up without waiting for the next interval.

**The mechanism itself does not guarantee "runs exactly once".** Gunicorn has
several workers and each has this thread. Not breaking when the same job runs concurrently
(being idempotent) is the responsibility of the job passed in.
"""

from __future__ import annotations

import logging
import threading
from collections.abc import Callable

logger = logging.getLogger(__name__)

_runners: list[PeriodicRunner] = []


class PeriodicRunner:
    def __init__(self, *, name: str, interval_seconds: float, task: Callable[[], None]) -> None:
        self._name = name
        self._interval_seconds = interval_seconds
        self._task = task
        self._stop_event = threading.Event()
        self._thread: threading.Thread | None = None

    def start(self) -> None:
        if self._thread is not None:
            return
        self._thread = threading.Thread(target=self._run, name=f"periodic-{self._name}", daemon=True)
        self._thread.start()
        logger.info(
            "Started periodic job: name=%s interval=%.0fs",
            self._name,
            self._interval_seconds,
            extra={"event": "scheduling.start"},
        )

    def stop(self) -> None:
        self._stop_event.set()

    def run_once(self) -> None:
        """Run one round. Exceptions stop here and are only recorded."""
        try:
            self._task()
        except Exception:
            logger.warning(
                "Periodic job failed: name=%s",
                self._name,
                exc_info=True,
                extra={"event": "scheduling.failed"},
            )

    def _run(self) -> None:
        self.run_once()
        while not self._stop_event.wait(self._interval_seconds):
            self.run_once()


def start_periodic_runner(*, name: str, interval_seconds: float, task: Callable[[], None]) -> PeriodicRunner | None:
    """Start a periodic job. Does nothing under tests (``TESTING``).

    It does not run under tests so that ``TestClient`` does not touch the DB from another
    thread on every startup. The job itself is tested by calling the use case directly.
    """
    from shared.kernel.settings.settings import settings

    if settings.testing:
        return None

    runner = PeriodicRunner(name=name, interval_seconds=interval_seconds, task=task)
    runner.start()
    _runners.append(runner)
    return runner


def stop_periodic_runners() -> None:
    """Stop a started periodic job (for process exit and test cleanup)."""
    for runner in _runners:
        runner.stop()
    _runners.clear()


__all__ = ["PeriodicRunner", "start_periodic_runner", "stop_periodic_runners"]
