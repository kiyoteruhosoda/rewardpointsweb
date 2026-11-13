"""Reading and writing system settings (used by the admin Config screen).

After saving, ``settings.reload_db_overrides()`` applies the change immediately. Settings read
only at startup (those with ``restart_scopes``) take effect only after a process restart, so the
save result reports "which settings need a restart of which service".
"""

from __future__ import annotations

import os
from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from typing import Any

from sqlalchemy.orm import Session

from presentation.fastapi.admin.system_settings_definitions import (
    SYSTEM_SETTING_DEFINITIONS,
    SYSTEM_SETTING_DEFINITIONS_BY_KEY,
)
from presentation.fastapi.admin.system_settings_validation import validate_system_settings
from shared.infrastructure.models import SystemSetting
from shared.kernel.outbound_destination import DestinationRefusedError, check_host_name
from shared.kernel.restart import ALL_RESTART_SCOPES, RestartScope
from shared.kernel.settings.settings import settings
from shared.kernel.settings.system_settings_defaults import DEFAULT_APPLICATION_SETTINGS, ENV_ONLY_SETTINGS

_SETTING_KEY = "app.config"
_SECRET_PLACEHOLDER = "********"

#: Destinations holding only a host name. Kept in the UI, but home-LAN / in-cluster ones are refused (ADR-0056).
_CHECKED_HOST_SETTINGS = frozenset({"MAIL_SERVER"})


class SettingRefusedError(ValueError):
    """A setting that cannot be saved. ``error`` is ``setting_env_only`` / ``invalid_destination``."""

    def __init__(self, error: str, key: str) -> None:
        super().__init__(error)
        self.error = error
        self.key = key


@dataclass(frozen=True)
class RestartRequirement:
    """Saved settings that need a restart to take effect."""

    scopes: tuple[RestartScope, ...]
    keys: tuple[str, ...]

    def __bool__(self) -> bool:
        return bool(self.keys)


@dataclass(frozen=True)
class SettingsSaveResult:
    """Result of a save.

    ``accepted_keys`` are the keys **actually taken into the save**. Unknown keys and secret
    fields sent back with their mask unchanged are excluded (both are silently discarded).
    If the recording side used "the requested keys", a save that changed nothing would be
    recorded as "settings changed", so this is what gets passed.
    """

    accepted_keys: tuple[str, ...]
    restart: RestartRequirement


class SystemSettingService:
    @staticmethod
    def stored_payload(session: Session) -> dict[str, Any]:
        row = session.get(SystemSetting, _SETTING_KEY)
        return dict(row.setting_json) if row and isinstance(row.setting_json, dict) else {}

    @classmethod
    def effective_config(cls, session: Session, env: Any = None) -> list[dict[str, Any]]:
        """Return definitions, current values and override state for the admin UI."""
        env = os.environ if env is None else env
        stored = cls.stored_payload(session)
        result = []
        for definition in SYSTEM_SETTING_DEFINITIONS:
            key = str(definition["key"])
            value = settings.resolve(key)
            if definition.get("secret") and value:
                value = _SECRET_PLACEHOLDER
            result.append(
                {
                    **definition,
                    "env_only": key in ENV_ONLY_SETTINGS,
                    "value": value,
                    # ⚠ **Not a lock flag.** DB values win over environment variables, so
                    #   it can still be changed from the UI when this is true. It means "this
                    #   key also has an env value = deleting the UI value falls back to it".
                    "env_fallback": bool(env.get(key)),
                    "stored": key in stored,
                    "default": DEFAULT_APPLICATION_SETTINGS.get(key),
                }
            )
        return result

    @classmethod
    def save(cls, session: Session, values: Mapping[str, Any], env: Any = None) -> SettingsSaveResult:
        """Save editable keys only. Unknown keys are silently discarded.

        Before writing, validate the combination of values that will be effective after the save.
        If it is inconsistent, raise and do not touch the DB at all (never save a broken config).

        The return value holds the accepted keys and those among them that need a restart.
        """
        for key, value in values.items():
            cls._ensure_acceptable(key, value)
        payload = cls.stored_payload(session)
        changed: list[str] = []
        for key, value in values.items():
            definition = SYSTEM_SETTING_DEFINITIONS_BY_KEY.get(key)
            if definition is None:
                continue
            # Do not clobber the real value when the mask is sent back unchanged
            if definition.get("secret") and value == _SECRET_PLACEHOLDER:
                continue
            if value is None:
                payload.pop(key, None)
            else:
                payload[key] = value
            changed.append(key)

        validate_system_settings(cls._effective_after_save(payload, env))

        row = session.get(SystemSetting, _SETTING_KEY)
        if row is None:
            session.add(SystemSetting(setting_key=_SETTING_KEY, setting_json=payload))
        else:
            row.setting_json = payload
        session.flush()
        settings.reload_db_overrides()
        return SettingsSaveResult(
            accepted_keys=tuple(sorted(set(changed))),
            restart=cls.restart_requirement(changed),
        )

    @staticmethod
    def _effective_after_save(payload: Mapping[str, Any], env: Any = None) -> dict[str, Any]:
        """Values ``settings`` will return after the save (environment > DB > default).

        Items pinned by environment variables have no effect when saved. Unless validation uses
        the values actually in effect, the UI shows a fix that does not actually work.
        """
        env = os.environ if env is None else env
        resolved: dict[str, Any] = {}
        for definition in SYSTEM_SETTING_DEFINITIONS:
            key = str(definition["key"])
            env_value = env.get(key)
            if env_value:
                resolved[key] = env_value
            elif key in payload:
                resolved[key] = payload[key]
            else:
                resolved[key] = DEFAULT_APPLICATION_SETTINGS.get(key)
        return resolved

    @staticmethod
    def _ensure_acceptable(key: str, value: Any) -> None:
        if key in ENV_ONLY_SETTINGS:
            raise SettingRefusedError("setting_env_only", key)
        if key in _CHECKED_HOST_SETTINGS and value:
            try:
                check_host_name(str(value))
            except DestinationRefusedError as error:
                raise SettingRefusedError("invalid_destination", key) from error

    @staticmethod
    def restart_requirement(keys: Iterable[str]) -> RestartRequirement:
        """Return which of *keys* need a restart to take effect, and the services concerned."""
        affected: list[str] = []
        scopes: set[RestartScope] = set()
        for key in sorted(set(keys)):
            definition = SYSTEM_SETTING_DEFINITIONS_BY_KEY.get(key)
            if definition is None:
                continue
            # Definitions are dict[str, object], so narrow to something iterable before passing
            raw_scopes = definition.get("restart_scopes")
            scope_values: Iterable[object] = raw_scopes if isinstance(raw_scopes, list | tuple) else ()
            parsed = RestartScope.parse_all(scope_values)
            if not parsed:
                continue
            affected.append(key)
            scopes.update(parsed)
        ordered = tuple(scope for scope in ALL_RESTART_SCOPES if scope in scopes)
        return RestartRequirement(scopes=ordered, keys=tuple(affected))


__all__ = ["RestartRequirement", "SettingsSaveResult", "SystemSettingService"]
