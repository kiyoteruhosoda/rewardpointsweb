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


class InvalidLogoutTokenError(IdentityFederationError):
    """``logout_token`` の検証に失敗した（署名・発行者・対象者・期限・形）。

    **理由は外へ出さない。** この口は未認証で叩けるので、細かく答えると
    「どこまで通ったか」を総当たりの手掛かりにできる。
    """

    code = "sso_invalid_logout_token"


class SsoAcrNotSatisfiedError(IdentityFederationError):
    """要求した認証の強度（``acr_values``）が満たされていない（ADR-0039）。

    ``acr`` が返ってこない場合もこれになる。要求したのに保証が得られていない以上、
    通してはいけない。
    """

    code = "sso_acr_not_satisfied"


class SsoEmailNotAllowedError(IdentityFederationError):
    """許可されていないメールドメイン。"""

    code = "sso_email_not_allowed"


class SsoAccountNotLinkedError(IdentityFederationError):
    """結び付く利用者が無い。

    このアプリは SSO で利用者を**作らない**（ADR-0029）。検証済みのメールアドレス
    が既存の利用者と一致しなければ、ここで断る。
    """

    code = "sso_account_not_linked"


class SsoIdentityTakenError(IdentityFederationError):
    """その IdP アカウントは**別の利用者**に結び付いている（ADR-0036）。

    ⚠ **横取りになるので断る。** 付け替えを許すと、IdP 側で 1 つの口座を共有して
    いる相手が、後からこのアプリの別人の入り口を奪える。
    """

    code = "sso_identity_taken"


class SsoAlreadyLinkedError(IdentityFederationError):
    """この利用者には、その IdP の結び付きが**既にある**（ADR-0036）。

    別の ``subject`` へ差し替えたいなら、いったん解除してから結び直す。黙って
    上書きすると、前の結び付きで入っていた経路が予告なく消える。
    """

    code = "sso_already_linked"


class SsoIdentityNotLinkedError(IdentityFederationError):
    """解除しようとしたが、その IdP との結び付きが無い。"""

    code = "sso_identity_not_linked"


class SsoLastEntranceError(IdentityFederationError):
    """解除すると、この利用者が**どこからも入れなくなる**（ADR-0036）。

    ⚠ **締め出しを作らない。** ローカルのパスワードもパスキーも無い利用者から
    IdP を外すと、残るのは管理者による復旧だけになる。
    """

    code = "sso_last_entrance"


class SsoLinkSessionMismatchError(IdentityFederationError):
    """連携の往復を始めた利用者と、戻ってきたときのセッションが違う。

    往復の途中でサインアウトした・別の利用者で入り直した場合に起きる。
    **どちらの口座へ結び付けるべきか決められない**ので、やり直してもらう。
    """

    code = "sso_link_session_mismatch"


class SsoAccountInactiveError(IdentityFederationError):
    """アカウントが無効化されている。"""

    code = "sso_account_inactive"


__all__ = [
    "IdentityFederationError",
    "IdentityProviderUnavailableError",
    "InvalidIdTokenError",
    "InvalidLogoutTokenError",
    "SsoAccountInactiveError",
    "SsoAccountNotLinkedError",
    "SsoAcrNotSatisfiedError",
    "SsoAlreadyLinkedError",
    "SsoEmailNotAllowedError",
    "SsoIdentityNotLinkedError",
    "SsoIdentityTakenError",
    "SsoLastEntranceError",
    "SsoLinkSessionMismatchError",
    "SsoLoginSessionNotFoundError",
    "SsoNotConfiguredError",
    "SsoTicketNotFoundError",
]
