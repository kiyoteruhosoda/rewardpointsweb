"""Single point of access to application settings.

Always read setting values through the ``@property`` accessors of this module's :data:`settings`
(:class:`ApplicationSettings`). Direct ``os.getenv`` or DB access is forbidden
(see the settings section of CLAUDE.md).

Priority: **environment variable > DB (system_settings table) > default value**.

Tests can create their own ``ApplicationSettings(env=...)`` to verify behaviour.
"""

from __future__ import annotations

import json
import logging
import os
import threading
import time
from collections.abc import Mapping, Sequence
from typing import Any

from shared.kernel.settings.system_settings_defaults import DEFAULT_APPLICATION_SETTINGS, ENV_ONLY_SETTINGS

_logger = logging.getLogger(__name__)

# Path of the redirect URI passed to the IdP (built when ``OIDC_REDIRECT_URI`` is unset).
# Keep in step with the router's definition (``bounded_contexts/identity_federation``).
OIDC_CALLBACK_PATH = "/api/auth/sso/callback"


class _DatabaseOverrides:
    """The DB layer of the "environment > DB > default" priority order.

    Supplies the ``app.config`` record of the ``system_settings`` table, which is saved from
    the admin UI.

    - When the DB is not connected or the table does not exist yet (before migrations), returns
      no values and keeps running on environment variables and defaults only. Logs one line
      only when entering / leaving the unreadable state.
    - Keeps a TTL cache to avoid DB access on every request. On save in the admin UI,
      ``SystemSettingService`` calls ``invalidate()`` so the change applies immediately.
    - Reads use a dedicated short-lived connection (so they do not disturb the
      transaction state of the shared session).
    """

    _SETTING_KEY = "app.config"
    _TTL_SECONDS = 10.0

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._loading = threading.local()
        self._payload: dict[str, Any] = {}
        self._expires_at = 0.0
        self._unreadable = False

    def invalidate(self) -> None:
        self._payload = {}
        self._expires_at = 0.0

    def get(self, key: str) -> Any:
        if key not in DEFAULT_APPLICATION_SETTINGS:
            # Only keys editable in the admin UI can be overridden from the DB. Resolving
            # bootstrap keys such as DATABASE_URI here would recurse.
            return None
        if getattr(self._loading, "active", False):
            return None
        if time.monotonic() >= self._expires_at:
            with self._lock:
                if time.monotonic() >= self._expires_at:
                    self._refresh()
        return self._payload.get(key)

    def _refresh(self) -> None:
        self._loading.active = True
        try:
            payload = self._load_payload()
            if payload is not None:
                self._payload = payload
            self._note_readable()
        except Exception:
            # Keep the last good values and do not retry until the next TTL
            self._note_unreadable()
        finally:
            self._loading.active = False
            self._expires_at = time.monotonic() + self._TTL_SECONDS

    def _note_unreadable(self) -> None:
        """Report that settings can no longer be read from the DB.

        Swallowing it silently leaves only the symptom "values saved in the admin UI have no
        effect", with the cause (DB not connected, before migrations) shown nowhere. Logging on
        every TTL would flood the log, though, so log one line **only when the state changes**.
        """
        if self._unreadable:
            return
        self._unreadable = True
        _logger.warning("system_settings_unreadable", exc_info=True)

    def _note_readable(self) -> None:
        if not self._unreadable:
            return
        self._unreadable = False
        _logger.info("system_settings_readable")

    def _load_payload(self) -> dict[str, Any] | None:
        from shared.kernel.settings.system_setting_records import (
            SystemSettingRecordReader,
        )

        value = SystemSettingRecordReader.read_json(self._SETTING_KEY)
        if value is None:
            return {}
        return value if isinstance(value, dict) else {}


class ApplicationSettings:
    """Returns setting values combining the DB, environment variables and defaults (in that order of precedence)."""

    def __init__(self, env: Mapping[str, str] | None = None) -> None:
        self._env: Mapping[str, str] = os.environ if env is None else env
        self._db = _DatabaseOverrides()

    # ------------------------------------------------------------------
    # Resolution logic
    # ------------------------------------------------------------------

    def _get(self, key: str, default: Any = None) -> Any:
        """⚠ **The DB (admin UI) wins over environment variables.**

        Environment variables are "initial values at deploy time"; **the place to change them
        during operation is the UI** — the other way round, once a single line is written in
        compose that key can no longer be touched from the UI, leaving it **shown on screen but
        impossible to change**.

        ⚠ **Bootstrap keys are outside this order** (e.g. `DATABASE_URI`).
        Reading from the DB a key that resolving the DB connection needs would recurse, so the
        section below reads `self._env` directly.
        """
        # ⚠ Endpoints and key locations are outside this order (ADR-0056). Ignore DB values for them.
        if key not in ENV_ONLY_SETTINGS:
            db_value = self._db.get(key)
            if db_value is not None:
                return db_value
        env_value = self._env.get(key)
        if env_value is not None and env_value != "":
            return env_value
        return DEFAULT_APPLICATION_SETTINGS.get(key, default)

    def resolve(self, key: str, default: Any = None) -> Any:
        """Resolve a key in priority order (for showing current values in the admin UI).

        Regular code must use the typed ``@property`` accessors.
        """
        return self._get(key, default)

    def get_bool(self, key: str, default: bool = False) -> bool:
        value = self._get(key, default)
        if isinstance(value, bool):
            return value
        if isinstance(value, str):
            return value.strip().lower() in {"1", "true", "yes", "on"}
        return bool(value)

    def get_int(self, key: str, default: int = 0) -> int:
        value = self._get(key, default)
        try:
            return int(value)
        except (TypeError, ValueError):
            return default

    def get_list(self, key: str) -> Sequence[str]:
        value = self._get(key, [])
        if isinstance(value, str):
            try:
                value = json.loads(value)
            except ValueError:
                value = [v.strip() for v in value.split(",") if v.strip()]
        return list(value) if isinstance(value, (list, tuple)) else []

    def reload_db_overrides(self) -> None:
        """Discard the DB override cache (right after saving settings, and for test cleanup)."""
        self._db.invalidate()

    # ------------------------------------------------------------------
    # Bootstrap (environment variables only; not overridable from the DB)
    # ------------------------------------------------------------------

    @property
    def testing(self) -> bool:
        return self.get_bool("TESTING", False)

    @property
    def database_uri(self) -> str:
        return self._env.get("DATABASE_URI") or "sqlite:///app.db"

    @property
    def admin_initial_password(self) -> str | None:
        return self._env.get("ADMIN_INITIAL_PASSWORD") or None

    # ------------------------------------------------------------------
    # Authentication
    # ------------------------------------------------------------------

    @property
    def secret_key(self) -> str:
        return str(self._get("SECRET_KEY"))

    @property
    def jwt_secret_key(self) -> str:
        return str(self._get("JWT_SECRET_KEY"))

    @property
    def access_token_issuer(self) -> str:
        return str(self._get("ACCESS_TOKEN_ISSUER"))

    @property
    def access_token_audience(self) -> str:
        return str(self._get("ACCESS_TOKEN_AUDIENCE"))

    @property
    def access_token_expires_seconds(self) -> int:
        return self.get_int("ACCESS_TOKEN_EXPIRES_SECONDS", 900)

    @property
    def refresh_token_expires_seconds(self) -> int:
        return self.get_int("REFRESH_TOKEN_EXPIRES_SECONDS", 14 * 24 * 3600)

    @property
    def session_cookie_secure(self) -> bool:
        return self.get_bool("SESSION_COOKIE_SECURE", False)

    @property
    def password_reset_token_ttl_seconds(self) -> int:
        return self.get_int("PASSWORD_RESET_TOKEN_TTL_SECONDS", 3600)

    @property
    def login_max_failures(self) -> int:
        """How many failures to allow within the window. ``0`` disables counting (never 0 in prod; ADR-0055)."""
        return max(self.get_int("LOGIN_MAX_FAILURES", 5), 0)

    @property
    def login_failure_window_seconds(self) -> int:
        return max(self.get_int("LOGIN_FAILURE_WINDOW_SECONDS", 900), 1)

    @property
    def login_lock_seconds(self) -> int:
        return max(self.get_int("LOGIN_LOCK_SECONDS", 900), 1)

    @property
    def temporary_password_ttl_seconds(self) -> int:
        """Lifetime of a temporary password issued by a parent (ADR-0011)."""
        return self.get_int("TEMPORARY_PASSWORD_TTL_SECONDS", 24 * 3600)

    @property
    def family_invitation_ttl_seconds(self) -> int:
        """Lifetime of an invitation code (ADR-0009)."""
        return self.get_int("FAMILY_INVITATION_TTL_SECONDS", 7 * 24 * 3600)

    # ------------------------------------------------------------------
    # Daily bonus (ADR-0024)
    # ------------------------------------------------------------------

    @property
    def daily_bonus_time_zone(self) -> str:
        """Time zone (IANA name) used to delimit a day."""
        return str(self._get("DAILY_BONUS_TIME_ZONE"))

    @property
    def daily_bonus_max_catch_up_days(self) -> int:
        """How many days of downtime to go back and grant retroactively."""
        return self.get_int("DAILY_BONUS_MAX_CATCH_UP_DAYS", 31)

    # ------------------------------------------------------------------
    # Two-factor authentication (TOTP)
    # ------------------------------------------------------------------

    @property
    def totp_issuer(self) -> str:
        return str(self._get("TOTP_ISSUER"))

    @property
    def totp_valid_window(self) -> int:
        return self.get_int("TOTP_VALID_WINDOW", 1)

    # ------------------------------------------------------------------
    # Passkeys (WebAuthn)
    # ------------------------------------------------------------------

    @property
    def webauthn_rp_id(self) -> str:
        return str(self._get("WEBAUTHN_RP_ID"))

    @property
    def webauthn_rp_name(self) -> str:
        return str(self._get("WEBAUTHN_RP_NAME"))

    @property
    def webauthn_origin(self) -> str:
        return str(self._get("WEBAUTHN_ORIGIN")).rstrip("/")

    @property
    def webauthn_challenge_ttl_seconds(self) -> int:
        return self.get_int("WEBAUTHN_CHALLENGE_TTL_SECONDS", 300)

    # ------------------------------------------------------------------
    # General
    # ------------------------------------------------------------------

    @property
    def app_base_url(self) -> str:
        return str(self._get("APP_BASE_URL") or "")

    @property
    def languages(self) -> Sequence[str]:
        return self.get_list("LANGUAGES")

    @property
    def default_locale(self) -> str:
        return str(self._get("DEFAULT_LOCALE"))

    @property
    def default_theme(self) -> str:
        return str(self._get("DEFAULT_THEME"))

    @property
    def cors_allowed_origins(self) -> Sequence[str]:
        return self.get_list("CORS_ALLOWED_ORIGINS")

    # ------------------------------------------------------------------
    # Mail
    # ------------------------------------------------------------------

    @property
    def mail_enabled(self) -> bool:
        return self.get_bool("MAIL_ENABLED", False)

    @property
    def mail_server(self) -> str:
        return str(self._get("MAIL_SERVER"))

    @property
    def mail_port(self) -> int:
        return self.get_int("MAIL_PORT", 587)

    @property
    def mail_use_tls(self) -> bool:
        return self.get_bool("MAIL_USE_TLS", True)

    @property
    def mail_use_ssl(self) -> bool:
        return self.get_bool("MAIL_USE_SSL", False)

    @property
    def mail_username(self) -> str:
        return str(self._get("MAIL_USERNAME") or "")

    @property
    def mail_password(self) -> str:
        return str(self._get("MAIL_PASSWORD") or "")

    @property
    def mail_default_sender(self) -> str:
        return str(self._get("MAIL_DEFAULT_SENDER") or "")

    # ------------------------------------------------------------------
    # External IdP (OIDC / SSO) integration. ADR-0029
    # ------------------------------------------------------------------

    @property
    def oidc_enabled(self) -> bool:
        """Whether SSO is used. **Does not check that the settings are complete** (:attr:`oidc_configured`)."""
        return self.get_bool("OIDC_ENABLED", False)

    @property
    def oidc_configured(self) -> bool:
        """Whether SSO can actually start (enabled and the endpoint is filled in).

        Whether credentials are complete differs per method, so ``ClientCredential`` decides that.
        This looks only at the endpoint.
        """
        return self.oidc_enabled and bool(self.oidc_issuer and self.oidc_client_id)

    @property
    def oidc_display_name(self) -> str:
        return str(self._get("OIDC_DISPLAY_NAME") or "SSO")

    @property
    def oidc_issuer(self) -> str:
        return str(self._get("OIDC_ISSUER") or "").rstrip("/")

    @property
    def oidc_client_id(self) -> str:
        return str(self._get("OIDC_CLIENT_ID") or "")

    @property
    def oidc_client_secret(self) -> str:
        return str(self._get("OIDC_CLIENT_SECRET") or "")

    @property
    def oidc_client_auth_method(self) -> str:
        """Client authentication method for the token endpoint.

        With ``private_key_jwt``, ``OIDC_CLIENT_SECRET`` is not used; instead an assertion signed
        with a private key on the host is presented. The benefit is that **the secret is in
        neither the deploy variables nor the DB**. Accepted values are ``CLIENT_AUTH_METHODS``
        in ``ClientCredential``.
        """
        return str(self._get("OIDC_CLIENT_AUTH_METHOD") or "").strip()

    @property
    def oidc_private_key_file(self) -> str:
        """Path of the private key (PEM) used for ``private_key_jwt``.

        On nolumialab ``/srv/secrets/oidc/client.key`` is passed in read-only.
        **Set the file's group to the container's runtime gid** (with 0400 root the app
        cannot read it). The directory itself also needs traverse permission.
        """
        return str(self._get("OIDC_PRIVATE_KEY_FILE") or "")

    @property
    def oidc_private_key_kid(self) -> str:
        """The ``kid`` put in the assertion header.

        When several keys are registered at the IdP, it cannot pick the key to verify with without it.
        """
        return str(self._get("OIDC_PRIVATE_KEY_KID") or "")

    @property
    def machine_client_id(self) -> str:
        """The ``client_id`` this app uses to identify itself **as a machine** (ADR-0040).

        ⚠ **A separate registration** from the one for user login (``OIDC_CLIENT_ID``). Only the key is shared.
        ⚠ **Do not name it after a purpose** (not ``RECONCILE_…``). Which app it belongs to is for
        assay to decide; this side does not declare a different identity per purpose.
        """
        return str(self._get("MACHINE_CLIENT_ID") or "")

    @property
    def oidc_scopes(self) -> Sequence[str]:
        return self.get_list("OIDC_SCOPES")

    @property
    def oidc_redirect_uri(self) -> str:
        """Redirect URI passed to the IdP. Built from :attr:`app_base_url` when unset."""
        configured = str(self._get("OIDC_REDIRECT_URI") or "")
        if configured:
            return configured
        base = self.app_base_url.rstrip("/")
        return f"{base}{OIDC_CALLBACK_PATH}" if base else ""

    @property
    def oidc_acr_values(self) -> Sequence[str]:
        """Required authentication strength. Empty = none required (ADR-0039)."""
        return self.get_list("OIDC_ACR_VALUES")

    @property
    def oidc_email_claim(self) -> str:
        return str(self._get("OIDC_EMAIL_CLAIM") or "email")

    @property
    def oidc_display_name_claim(self) -> str:
        return str(self._get("OIDC_DISPLAY_NAME_CLAIM") or "name")

    @property
    def oidc_link_by_email(self) -> bool:
        """Whether a first login is merged into an existing user with the same email (ADR-0033).

        ⚠ **Not merged by default.** If the IdP's meaning of the ``email_verified`` condition
        differs from ours, claiming someone's address alone becomes a way into their account.

        ⚠ While false, **a person who has an account with the same email is refused at first SSO**
        (no second account is created; ADR-0041). They sign into that account and link it from settings.
        """
        return self.get_bool("OIDC_LINK_BY_EMAIL", False)

    @property
    def oidc_allowed_email_domains(self) -> Sequence[str]:
        return self.get_list("OIDC_ALLOWED_EMAIL_DOMAINS")

    @property
    def oidc_login_session_ttl_seconds(self) -> int:
        return self.get_int("OIDC_LOGIN_SESSION_TTL_SECONDS", 600)

    @property
    def oidc_login_ticket_ttl_seconds(self) -> int:
        return self.get_int("OIDC_LOGIN_TICKET_TTL_SECONDS", 60)

    # ------------------------------------------------------------------
    # Logging
    # ------------------------------------------------------------------

    @property
    def log_level(self) -> str:
        return str(self._get("LOG_LEVEL"))

    @property
    def log_to_database(self) -> bool:
        return self.get_bool("LOG_TO_DATABASE", True)


settings = ApplicationSettings()

__all__ = ["OIDC_CALLBACK_PATH", "ApplicationSettings", "settings"]
