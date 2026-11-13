"""Setting item definitions for the admin console (Config).

When adding a key, also update ``system_settings_defaults.py`` and ``settings.py``
(see CLAUDE.md "Settings management").

Keys of each item:

- ``key`` / ``category`` / ``value_type``: required.
- ``label``: default English label. Display text is translated in the frontend
  (it keeps ``config.field.<KEY>`` in its dictionary and falls back to this label).
- ``secret``: the value is never returned to the screen (masked as ``********``).
- ``choices``: items with choices. Pairs of value and display label.
- ``restart_scopes``: set on settings **only read at startup**. On save the admin console
  shows "restart required" and a restart can be requested from there
  (:mod:`shared.kernel.restart`). If empty, the value takes effect on save.
"""

from __future__ import annotations

from shared.kernel.restart import RestartScope

# Settings only read at startup (evaluated once in the application factory)
_RESTART_WEB: tuple[str, ...] = (RestartScope.WEB.value,)

SYSTEM_SETTING_DEFINITIONS: list[dict[str, object]] = [
    # --- Authentication ---
    {
        # ⚠ **This is the upper bound on "time until a suspension takes effect"** (ADR-0037). Verification
        #   does not hit the DB, so a suspended user is rejected only when the next token is issued.
        "key": "ACCESS_TOKEN_EXPIRES_SECONDS",
        "category": "auth",
        "label": "Access token lifetime (seconds)",
        "value_type": "integer",
    },
    {
        "key": "REFRESH_TOKEN_EXPIRES_SECONDS",
        "category": "auth",
        "label": "Refresh token lifetime (seconds)",
        "value_type": "integer",
    },
    {
        "key": "SESSION_COOKIE_SECURE",
        "category": "auth",
        "label": "Secure cookie (HTTPS only)",
        "value_type": "boolean",
    },
    {
        "key": "PASSWORD_RESET_TOKEN_TTL_SECONDS",
        "category": "auth",
        "label": "Password reset token TTL (seconds)",
        "value_type": "integer",
    },
    {
        "key": "LOGIN_MAX_FAILURES",
        "category": "auth",
        "label": "Login failures allowed per window (0 = unlimited)",
        "value_type": "integer",
    },
    {
        "key": "LOGIN_FAILURE_WINDOW_SECONDS",
        "category": "auth",
        "label": "Login failure window (seconds)",
        "value_type": "integer",
    },
    {
        "key": "LOGIN_LOCK_SECONDS",
        "category": "auth",
        "label": "Login lock duration after too many failures (seconds)",
        "value_type": "integer",
    },
    {
        "key": "TEMPORARY_PASSWORD_TTL_SECONDS",
        "category": "auth",
        "label": "Temporary password TTL (seconds)",
        "value_type": "integer",
    },
    {
        "key": "FAMILY_INVITATION_TTL_SECONDS",
        "category": "auth",
        "label": "Family invitation code TTL (seconds)",
        "value_type": "integer",
    },
    # --- Families (reward_points context) ---
    {
        "key": "DAILY_BONUS_TIME_ZONE",
        "category": "family",
        "label": "Daily bonus day boundary (IANA time zone)",
        "value_type": "string",
    },
    {
        "key": "DAILY_BONUS_MAX_CATCH_UP_DAYS",
        "category": "family",
        "label": "Daily bonus catch-up limit (days)",
        "value_type": "integer",
    },
    # --- Two-factor authentication (TOTP) ---
    {
        "key": "TOTP_ISSUER",
        "category": "two_factor",
        "label": "Issuer shown in authenticator apps",
        "value_type": "string",
    },
    {
        "key": "TOTP_VALID_WINDOW",
        "category": "two_factor",
        "label": "Accepted time-step drift",
        "value_type": "integer",
    },
    # --- Passkeys (WebAuthn) ---
    {"key": "WEBAUTHN_RP_ID", "category": "passkey", "label": "Relying party ID (domain)", "value_type": "string"},
    {"key": "WEBAUTHN_RP_NAME", "category": "passkey", "label": "Relying party name", "value_type": "string"},
    {"key": "WEBAUTHN_ORIGIN", "category": "passkey", "label": "Expected browser origin", "value_type": "string"},
    {
        "key": "WEBAUTHN_CHALLENGE_TTL_SECONDS",
        "category": "passkey",
        "label": "Challenge lifetime (seconds)",
        "value_type": "integer",
    },
    # --- External IdP (OIDC / SSO). ADR-0029 ---
    {"key": "OIDC_ENABLED", "category": "sso", "label": "Enable SSO (OpenID Connect)", "value_type": "boolean"},
    {"key": "OIDC_DISPLAY_NAME", "category": "sso", "label": "Sign-in button label", "value_type": "string"},
    {"key": "OIDC_ISSUER", "category": "sso", "label": "Issuer URL", "value_type": "string"},
    {"key": "OIDC_CLIENT_ID", "category": "sso", "label": "Client ID", "value_type": "string"},
    {
        "key": "OIDC_CLIENT_SECRET",
        "category": "sso",
        "label": "Client secret",
        "value_type": "string",
        "secret": True,
    },
    {
        "key": "OIDC_CLIENT_AUTH_METHOD",
        "category": "sso",
        "label": "Client authentication",
        "value_type": "string",
        "choices": [["client_secret_basic", "Client secret"], ["private_key_jwt", "Private key (JWT)"]],
    },
    {
        "key": "OIDC_PRIVATE_KEY_FILE",
        "category": "sso",
        "label": "Private key file (private_key_jwt only)",
        "value_type": "string",
    },
    {
        "key": "OIDC_PRIVATE_KEY_KID",
        "category": "sso",
        "label": "Private key ID (blank = the IdP has only one key)",
        "value_type": "string",
    },
    {
        "key": "MACHINE_CLIENT_ID",
        "category": "sso",
        "label": "Service account client ID (empty = do not reconcile with the identity provider)",
        "value_type": "string",
    },
    {"key": "OIDC_SCOPES", "category": "sso", "label": "Requested scopes", "value_type": "list"},
    {
        "key": "OIDC_REDIRECT_URI",
        "category": "sso",
        "label": "Redirect URI (blank = base URL + callback path)",
        "value_type": "string",
    },
    {
        "key": "OIDC_ACR_VALUES",
        "category": "sso",
        "label": "Required authentication context (acr_values, empty = do not request)",
        "value_type": "list",
    },
    {"key": "OIDC_EMAIL_CLAIM", "category": "sso", "label": "Email claim", "value_type": "string"},
    {"key": "OIDC_DISPLAY_NAME_CLAIM", "category": "sso", "label": "Display name claim", "value_type": "string"},
    {
        "key": "OIDC_LINK_BY_EMAIL",
        "category": "sso",
        "label": "Link to an existing account by verified email (check what the IdP means by verified)",
        "value_type": "boolean",
    },
    {
        "key": "OIDC_ALLOWED_EMAIL_DOMAINS",
        "category": "sso",
        "label": "Allowed email domains (blank = any)",
        "value_type": "list",
    },
    {
        "key": "OIDC_LOGIN_SESSION_TTL_SECONDS",
        "category": "sso",
        "label": "Authorization request lifetime (seconds)",
        "value_type": "integer",
    },
    {
        "key": "OIDC_LOGIN_TICKET_TTL_SECONDS",
        "category": "sso",
        "label": "Hand-off ticket lifetime (seconds)",
        "value_type": "integer",
    },
    # --- General ---
    {"key": "APP_BASE_URL", "category": "general", "label": "Application base URL", "value_type": "string"},
    {"key": "LANGUAGES", "category": "general", "label": "Selectable languages", "value_type": "list"},
    {
        "key": "DEFAULT_LOCALE",
        "category": "general",
        "label": "Default locale",
        "value_type": "string",
        "choices": [["en", "English"], ["ja", "日本語"]],
    },
    {
        "key": "DEFAULT_THEME",
        "category": "general",
        "label": "Default theme",
        "value_type": "string",
        "choices": [["system", "Follow the OS"], ["light", "Light"], ["dark", "Dark"]],
    },
    {
        "key": "CORS_ALLOWED_ORIGINS",
        "category": "general",
        "label": "CORS allowed origins",
        "value_type": "list",
        "restart_scopes": _RESTART_WEB,
    },
    # --- Mail ---
    {"key": "MAIL_ENABLED", "category": "mail", "label": "Enable mail sending", "value_type": "boolean"},
    {"key": "MAIL_SERVER", "category": "mail", "label": "SMTP server", "value_type": "string"},
    {"key": "MAIL_PORT", "category": "mail", "label": "SMTP port", "value_type": "integer"},
    {"key": "MAIL_USE_TLS", "category": "mail", "label": "Use STARTTLS", "value_type": "boolean"},
    {"key": "MAIL_USE_SSL", "category": "mail", "label": "Use SSL", "value_type": "boolean"},
    {"key": "MAIL_USERNAME", "category": "mail", "label": "SMTP username", "value_type": "string"},
    {"key": "MAIL_PASSWORD", "category": "mail", "label": "SMTP password", "value_type": "string", "secret": True},
    {"key": "MAIL_DEFAULT_SENDER", "category": "mail", "label": "Default sender address", "value_type": "string"},
    # --- Logging ---
    {
        "key": "LOG_LEVEL",
        "category": "logging",
        "label": "Log level",
        "value_type": "string",
        "choices": [["DEBUG", "DEBUG"], ["INFO", "INFO"], ["WARNING", "WARNING"], ["ERROR", "ERROR"]],
        "restart_scopes": _RESTART_WEB,
    },
    {
        "key": "LOG_TO_DATABASE",
        "category": "logging",
        "label": "Write logs to database",
        "value_type": "boolean",
        "restart_scopes": _RESTART_WEB,
    },
]

SYSTEM_SETTING_DEFINITIONS_BY_KEY: dict[str, dict[str, object]] = {
    str(definition["key"]): definition for definition in SYSTEM_SETTING_DEFINITIONS
}

__all__ = ["SYSTEM_SETTING_DEFINITIONS", "SYSTEM_SETTING_DEFINITIONS_BY_KEY"]
