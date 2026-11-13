"""Default values of system settings (priority: environment variable > DB > here).

When adding a key, also update the ``@property`` in ``settings.py`` and
``presentation/fastapi/admin/system_settings_definitions.py``
(see the settings section of CLAUDE.md).
"""

from __future__ import annotations

DEFAULT_APPLICATION_SETTINGS: dict[str, object] = {
    # --- Authentication ---
    "SECRET_KEY": "default-secret-key",
    "JWT_SECRET_KEY": "default-jwt-secret-change-me-in-production",
    "ACCESS_TOKEN_ISSUER": "rewardpointsweb",
    "ACCESS_TOKEN_AUDIENCE": "rewardpointsweb",
    "ACCESS_TOKEN_EXPIRES_SECONDS": 300,
    "REFRESH_TOKEN_EXPIRES_SECONDS": 14 * 24 * 3600,
    "SESSION_COOKIE_SECURE": False,
    "PASSWORD_RESET_TOKEN_TTL_SECONDS": 3600,
    # Failure limit per login identifier (ADR-0055). Reaching it within the window refuses for a while
    "LOGIN_MAX_FAILURES": 5,
    "LOGIN_FAILURE_WINDOW_SECONDS": 900,
    "LOGIN_LOCK_SECONDS": 900,
    # Lifetime of a temporary password issued by a parent (ADR-0011)
    "TEMPORARY_PASSWORD_TTL_SECONDS": 24 * 3600,
    # --- Family (reward_points context) ---
    "FAMILY_INVITATION_TTL_SECONDS": 7 * 24 * 3600,
    # Day boundary for the daily bonus (ADR-0024). Stored times are always UTC, but cutting
    # "every day" at 00:00 UTC makes the date change at 9:00 every morning in Japan.
    # Families who want it to follow their everyday day change it to e.g. Asia/Tokyo (IANA name)
    "DAILY_BONUS_TIME_ZONE": "UTC",
    # How many days of downtime to go back and grant. Anything beyond is not granted
    # (so a ledger opened after a long time is not filled with hundreds of bonus rows)
    "DAILY_BONUS_MAX_CATCH_UP_DAYS": 31,
    # --- Two-factor authentication (TOTP) ---
    "TOTP_ISSUER": "rewardpointsweb",  # Issuer name shown in authenticator apps
    "TOTP_VALID_WINDOW": 1,  # How many time steps either side to accept (absorbs clock drift)
    # --- Passkeys (WebAuthn) ---
    # The RP ID is what registered passkeys are bound to. Changing it invalidates existing passkeys.
    # It can only be **a domain name** (no IP addresses), so during development open
    # localhost rather than 127.0.0.1 (mapping table in docs/OPERATIONS.md).
    "WEBAUTHN_RP_ID": "localhost",
    "WEBAUTHN_RP_NAME": "rewardpointsweb",
    "WEBAUTHN_ORIGIN": "http://localhost:5173",
    "WEBAUTHN_CHALLENGE_TTL_SECONDS": 300,
    # --- External IdP (OIDC / SSO) integration. ADR-0029 ---
    # Disabled by default. Enabling it requires ISSUER / CLIENT_ID and the credential for the
    # chosen method (CLIENT_SECRET or PRIVATE_KEY_FILE) (if any is missing, it is treated
    # as "disabled").
    "OIDC_ENABLED": False,
    "OIDC_DISPLAY_NAME": "SSO",  # Name shown on the login screen button
    # Issuer URL of the OpenID Provider. It must be readable with /.well-known/openid-configuration
    # appended (each endpoint is looked up via discovery).
    "OIDC_ISSUER": "",
    "OIDC_CLIENT_ID": "",
    "OIDC_CLIENT_SECRET": "",
    # Client authentication method for the token endpoint.
    # client_secret_basic = use CLIENT_SECRET above.
    # private_key_jwt     = sign with the private key in PRIVATE_KEY_FILE below (keeps the
    #                       secret out of both the deploy variables and the DB).
    "OIDC_CLIENT_AUTH_METHOD": "client_secret_basic",
    # Used only with private_key_jwt. Pass the PEM on the host in read-only.
    "OIDC_PRIVATE_KEY_FILE": "",
    # When several keys are registered at the IdP, tells it which one to verify with (RFC 7638
    # thumbprint). May be empty if there is only one.
    "OIDC_PRIVATE_KEY_KID": "",
    # client_id this app uses when calling the IdP **as a machine** (ADR-0040). Registered in assay
    # as a service account; a separate registration from OIDC_CLIENT_ID used for login.
    # Shares the key from OIDC_PRIVATE_KEY_FILE / KID above; the method is always private_key_jwt.
    # Empty means periodic reconciliation does not run. ⚠ Skipped with 403 until it is bound to
    # the app's identity in assay.
    "MACHINE_CLIENT_ID": "",
    "OIDC_SCOPES": ["openid", "profile", "email"],
    # Redirect URI registered at the IdP. Empty means APP_BASE_URL + /api/auth/sso/callback.
    "OIDC_REDIRECT_URI": "",
    # Required authentication strength (``acr_values``). Empty = none required (ADR-0039).
    # ⚠ **Setting it makes login fail closed.** If the returned acr does not match the request
    #   (or none is returned) the login is refused. Leave it empty when connecting to an IdP
    #   without such reserved values. With our own idp (assay), urn:assay:ac:mfa is available.
    "OIDC_ACR_VALUES": [],
    # Claim name mapping (differs per IdP)
    "OIDC_EMAIL_CLAIM": "email",
    "OIDC_DISPLAY_NAME_CLAIM": "name",
    # Accepted email domains (empty = no restriction)
    # ⚠ **Whether a first login is merged into an existing user. Default is false** (ADR-0033).
    #   With our own idp (assay), the email_verified condition means "the tenant admin claims
    #   so", not proof from the person themselves.
    #   ⚠ While false, a person who has an account with the same email is refused at first SSO
    #   (no second account is created; ADR-0041). They sign into that account and link it from settings.
    "OIDC_LINK_BY_EMAIL": False,
    "OIDC_ALLOWED_EMAIL_DOMAINS": [],
    # Time allowed for the authorization request -> callback round trip
    "OIDC_LOGIN_SESSION_TTL_SECONDS": 600,
    # Lifetime of the ticket issued by the callback (which the SPA exchanges for tokens)
    "OIDC_LOGIN_TICKET_TTL_SECONDS": 60,
    # --- General ---
    "APP_BASE_URL": "",  # Base for password reset links etc. (e.g. https://app.example.com)
    "LANGUAGES": ["en", "ja"],
    "DEFAULT_LOCALE": "en",
    "DEFAULT_THEME": "light",  # system / light / dark
    "CORS_ALLOWED_ORIGINS": [],
    # --- Mail ---
    "MAIL_ENABLED": False,
    "MAIL_SERVER": "smtp.example.com",
    "MAIL_PORT": 587,
    "MAIL_USE_TLS": True,
    "MAIL_USE_SSL": False,
    "MAIL_USERNAME": "",
    "MAIL_PASSWORD": "",
    "MAIL_DEFAULT_SENDER": "",
    # --- Logging ---
    "LOG_LEVEL": "INFO",
    "LOG_TO_DATABASE": True,
}

#: Settings decided by environment variables only (ADR-0056): where the server connects to, and
#: where the key file is. Shown read-only in the admin UI; saving is refused. Stale DB values are ignored.
ENV_ONLY_SETTINGS: frozenset[str] = frozenset(
    {
        "OIDC_ISSUER",
        "OIDC_PRIVATE_KEY_FILE",
    }
)

__all__ = ["DEFAULT_APPLICATION_SETTINGS", "ENV_ONLY_SETTINGS"]
