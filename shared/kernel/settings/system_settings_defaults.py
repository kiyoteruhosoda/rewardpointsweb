"""システム設定のデフォルト値（優先順位: 環境変数 > DB > ここ）。

キーを追加したら ``settings.py`` の ``@property`` と
``presentation/fastapi/admin/system_settings_definitions.py`` も更新する
（CLAUDE.md「設定管理」参照）。
"""

from __future__ import annotations

DEFAULT_APPLICATION_SETTINGS: dict[str, object] = {
    # --- 認証 ---
    "SECRET_KEY": "default-secret-key",
    "JWT_SECRET_KEY": "default-jwt-secret-change-me-in-production",
    "ACCESS_TOKEN_ISSUER": "rewardpointsweb",
    "ACCESS_TOKEN_AUDIENCE": "rewardpointsweb",
    "ACCESS_TOKEN_EXPIRES_SECONDS": 900,
    "REFRESH_TOKEN_EXPIRES_SECONDS": 14 * 24 * 3600,
    "SESSION_COOKIE_SECURE": False,
    "PASSWORD_RESET_TOKEN_TTL_SECONDS": 3600,
    # 親が発行した一時パスワードの有効期限（ADR-0011）
    "TEMPORARY_PASSWORD_TTL_SECONDS": 24 * 3600,
    # --- 家族（reward_points コンテキスト） ---
    "FAMILY_INVITATION_TTL_SECONDS": 7 * 24 * 3600,
    # 毎日のボーナス（ADR-0024）の 1 日の区切り。保存する時刻は常に UTC だが、
    # 「毎日」を UTC の 0 時で切ると日本では毎朝 9 時が日付の変わり目になる。
    # 暮らしの側の 1 日に合わせたい家族は Asia/Tokyo 等へ変える（IANA 名）
    "DAILY_BONUS_TIME_ZONE": "UTC",
    # 止まっていたあいだの何日分まで遡って渡すか。超えた分は渡さない
    # （久しぶりに開いた台帳が何百行ものボーナスで埋まらないようにする）
    "DAILY_BONUS_MAX_CATCH_UP_DAYS": 31,
    # --- 二要素認証（TOTP） ---
    "TOTP_ISSUER": "rewardpointsweb",  # 認証アプリに表示される発行者名
    "TOTP_VALID_WINDOW": 1,  # 前後いくつの時間枠を許容するか（時刻ずれ吸収）
    # --- パスキー（WebAuthn） ---
    # RP ID は登録済みパスキーの結び付け先。変更すると既存のパスキーが無効になる。
    # 指定できるのは**ドメイン名のみ**（IP アドレス不可）。そのため開発時は
    # 127.0.0.1 ではなく localhost で開く（docs/OPERATIONS.md に対応表）。
    "WEBAUTHN_RP_ID": "localhost",
    "WEBAUTHN_RP_NAME": "rewardpointsweb",
    "WEBAUTHN_ORIGIN": "http://localhost:5173",
    "WEBAUTHN_CHALLENGE_TTL_SECONDS": 300,
    # --- 一般 ---
    "APP_BASE_URL": "",  # パスワードリセットリンク等の生成元（例: https://app.example.com）
    "LANGUAGES": ["en", "ja"],
    "DEFAULT_LOCALE": "en",
    "DEFAULT_THEME": "light",  # system / light / dark
    "CORS_ALLOWED_ORIGINS": [],
    # --- メール ---
    "MAIL_ENABLED": False,
    "MAIL_SERVER": "smtp.example.com",
    "MAIL_PORT": 587,
    "MAIL_USE_TLS": True,
    "MAIL_USE_SSL": False,
    "MAIL_USERNAME": "",
    "MAIL_PASSWORD": "",
    "MAIL_DEFAULT_SENDER": "",
    # --- ログ ---
    "LOG_LEVEL": "INFO",
    "LOG_TO_DATABASE": True,
}

__all__ = ["DEFAULT_APPLICATION_SETTINGS"]
