"""Reading JSON records from the ``system_settings`` table.

The DB override layer of ``settings`` (:mod:`shared.kernel.settings.settings`) and the restart
request store (:mod:`shared.kernel.restart.request`) share the same situation: both "read one
``system_settings`` row from outside a request". The read must use a **dedicated short-lived
connection**, because using the shared session would let the watcher thread or setting
resolution pollute the request's transaction state.

It is collected here so both do not carry the same raw SQL. Writes use the normal
ORM session (inside a request), so only reading lives here.
"""

from __future__ import annotations

import json
from typing import Any

from sqlalchemy import text

_SELECT_SETTING_JSON = text("SELECT setting_json FROM system_settings WHERE setting_key = :key")


class SystemSettingRecordReader:
    """Read one ``system_settings`` row over a short-lived connection."""

    @staticmethod
    def read_json(setting_key: str) -> Any | None:
        """Return ``setting_json`` for *setting_key*, or ``None`` if there is no row.

        No DB connection or a missing table (before migration) propagates as an exception.
        It is not swallowed here so callers can tell "no value" from
        "could not read".
        """
        from shared.kernel.database.db import get_engine

        with get_engine().connect() as connection:
            row = connection.execute(_SELECT_SETTING_JSON, {"key": setting_key}).first()
        if row is None:
            return None
        value = row[0]
        # Some drivers return MariaDB JSON columns as strings
        return json.loads(value) if isinstance(value, str) else value


__all__ = ["SystemSettingRecordReader"]
