"""ID 連携コンテキストのドメイン例外。

``code`` がそのまま API のエラーコード（表示文言はフロントエンド）になる。
ブラウザの往復の途中で起きた失敗は、ログイン画面へ ``?sso_error=<code>`` として
返る（ADR-0029）。
"""

from __future__ import annotations


class IdentityFederationError(Exception):
    """このコンテキストの基底例外。"""

    code = "sso_error"


class SsoNotConfiguredError(IdentityFederationError):
    """SSO が無効、または接続先（issuer / client）が埋まっていない。"""

    code = "sso_not_configured"


class SsoLoginSessionNotFoundError(IdentityFederationError):
    """認可要求の控えが見つからない（``state`` の不一致・期限切れ・使用済み）。"""

    code = "sso_state_invalid"


class SsoTicketNotFoundError(IdentityFederationError):
    """引き換え券が見つからない（期限切れ・使用済み）。"""

    code = "sso_ticket_invalid"


class IdentityProviderUnavailableError(IdentityFederationError):
    """IdP と話せない（discovery・トークン交換の通信／応答の失敗）。"""

    code = "sso_provider_unavailable"


class InvalidIdTokenError(IdentityFederationError):
    """ID トークンの検証に失敗した（署名・発行者・対象者・nonce）。"""

    code = "sso_invalid_id_token"


class SsoEmailMissingError(IdentityFederationError):
    """メールアドレスのクレームが無い（アカウントを結び付けられない）。"""

    code = "sso_email_missing"


class SsoEmailNotAllowedError(IdentityFederationError):
    """許可されていないメールドメイン。"""

    code = "sso_email_not_allowed"


class SsoAccountNotLinkedError(IdentityFederationError):
    """結び付く利用者が無い。

    このアプリは SSO で利用者を**作らない**（ADR-0029）。検証済みのメールアドレス
    が既存の利用者と一致しなければ、ここで断る。
    """

    code = "sso_account_not_linked"


class SsoAccountInactiveError(IdentityFederationError):
    """アカウントが無効化されている。"""

    code = "sso_account_inactive"


__all__ = [
    "IdentityFederationError",
    "IdentityProviderUnavailableError",
    "InvalidIdTokenError",
    "SsoAccountInactiveError",
    "SsoAccountNotLinkedError",
    "SsoEmailMissingError",
    "SsoEmailNotAllowedError",
    "SsoLoginSessionNotFoundError",
    "SsoNotConfiguredError",
    "SsoTicketNotFoundError",
]
