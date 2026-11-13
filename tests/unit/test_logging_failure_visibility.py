"""When the logging infrastructure itself fails, that is visible.

If the log writer swallows exceptions, the symptoms are only "no logs in the admin screen" and "saved settings
have no effect", and the cause (DB not connected, before migration, column mismatch) is
left nowhere. This checks that we **neither stop processing nor stay silent**.
"""

from __future__ import annotations

import logging

import pytest

from shared.kernel.logging.db_log_handler import DbLogHandler
from shared.kernel.settings.settings import ApplicationSettings


def _record() -> logging.LogRecord:
    return logging.LogRecord("test", logging.INFO, __file__, 1, "hello", None, None)


def test_write_failure_does_not_propagate(monkeypatch: pytest.MonkeyPatch) -> None:
    """The main work is not brought down for logging's sake."""
    handler = DbLogHandler()
    monkeypatch.setattr(handler, "handleError", _ignore)
    monkeypatch.setattr(
        "shared.kernel.logging.db_log_handler.write_log_rows",
        _raise,
    )

    handler.emit(_record())  # no exception leaks


def test_write_failure_is_reported(monkeypatch: pytest.MonkeyPatch) -> None:
    """Failures are reported via ``handleError`` (stderr). Not silently dropped."""
    handler = DbLogHandler()
    reported: list[logging.LogRecord] = []
    monkeypatch.setattr(handler, "handleError", reported.append)
    monkeypatch.setattr(
        "shared.kernel.logging.db_log_handler.write_log_rows",
        _raise,
    )

    record = _record()
    handler.emit(record)

    assert reported == [record]


def _raise(rows: object) -> None:
    raise RuntimeError("database is locked")


def _ignore(record: logging.LogRecord) -> None:
    """Replacement for ``handleError`` (keeps stderr clean during tests)."""


def test_unreadable_system_settings_are_reported_once(caplog: pytest.LogCaptureFixture) -> None:
    """Warn only once when settings cannot be read from the DB (warning every TTL would flood)."""
    settings = ApplicationSettings(env={})

    with caplog.at_level(logging.DEBUG, logger="shared.kernel.settings.settings"):
        # No engine configured = unreadable. Collapse the TTL and read twice
        assert settings.log_level == "INFO"
        settings.reload_db_overrides()
        assert settings.log_level == "INFO"

    messages = [record.message for record in caplog.records]
    assert messages.count("system_settings_unreadable") == 1
