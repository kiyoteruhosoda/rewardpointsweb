"""認可マスタデータの正本（ユビキタス言語: ロール / 権限 / 権限付与）。

ロール・権限コード・ロールへの権限付与・初期管理者は、アプリケーションが
起動時から正しく動作するために必須の「マスタデータ」である。値の重複定義に
よるドリフトを防ぐため、ここを唯一の出所（single source of truth）とし、

- マイグレーション（``migrations/versions/*_seed_master_data.py``）
- 投入スクリプト（``scripts/seed_master_data.py``）

の双方がこのモジュールを参照する。フレームワーク・DB に依存しない純データの
ため、どこからでも安全に import できる。
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence

# --- ロール ------------------------------------------------------------------
# id は外部参照（user_roles 等）の安定キーとして固定する。
ROLES: Sequence[tuple[int, str]] = (
    (1, "admin"),
    (2, "manager"),
    (3, "member"),
    (4, "guest"),
)

# --- 権限コード（scope） -----------------------------------------------------
# 認可は scope（権限コード値）で行う。コードを安定キーとし、id は DB 採番に任せる。
PERMISSION_CODES: Sequence[str] = (
    "admin:system-settings",
    "user:manage",
    "role:manage",
    "permission:manage",
    "system:manage",
    "log:view",
    "dashboard:view",
    "gui:view",
    "item:view",
    "item:manage",
    # --- ポイント（reward_points コンテキスト） ---
    # scope は「その操作を行える立場か」までを決める。「その家族・その台帳を
    # 触れるか」は家族の中での立場（role）で別に判定する（ADR-0009）。
    "family:view",
    "family:manage",
    "point:view",
    "point:manage",
)

# --- ロールへの権限付与 ------------------------------------------------------
# ロール名 -> 付与する権限コードの集合。有効 scope は所属ロールの和集合。
ROLE_PERMISSIONS: Mapping[str, Sequence[str]] = {
    "admin": tuple(PERMISSION_CODES),  # 全権限
    "manager": (
        "item:view",
        "item:manage",
        "log:view",
        "dashboard:view",
        "gui:view",
        # 家族を作り、子を追加し、ポイントを加算・消費できる
        "family:view",
        "family:manage",
        "point:view",
        "point:manage",
    ),
    "member": (
        "item:view",
        "dashboard:view",
        "gui:view",
        # 自分のポイントと履歴は見られるが、変更する scope は持たない
        "family:view",
        "point:view",
    ),
    "guest": (
        "dashboard:view",
        "gui:view",
    ),
}

# --- 初期管理者 --------------------------------------------------------------
# ログインの識別子は ``username``（ADR-0011）。既定値をメールアドレスと同じ文字列に
# しているのは、既存アカウントの移行値が ``username = email`` になるためで、
# 移行前後でログインの手順を変えないための選択。
#
# パスワードは環境変数 ``ADMIN_INITIAL_PASSWORD`` で上書きできる（推奨）。
# 未指定時は既定のパスワード（メールアドレスと同じ文字列）が使われる。誰でも
# 知り得る値なので、本番では初回ログイン後に必ず変更すること。
#
# 平文とハッシュの両方を置くのは、平文が公開の既定値（秘密ではない）であり、
# ドキュメントとハッシュの食い違いを検出できるようにするため
# （``tests/unit/test_master_data.py`` が両者の一致を検証する）。ハッシュ化は
# Infrastructure の関心なので、この層では計算せず定数として持つ。
DEFAULT_ADMIN_ID: int = 1
DEFAULT_ADMIN_EMAIL: str = "admin@example.com"
DEFAULT_ADMIN_USERNAME: str = "admin@example.com"
DEFAULT_ADMIN_DISPLAY_NAME: str = "admin"
DEFAULT_ADMIN_ROLE: str = "admin"
DEFAULT_ADMIN_PASSWORD: str = "admin@example.com"
DEFAULT_ADMIN_PASSWORD_HASH: str = (
    "scrypt:32768:8:1$fxv8GEDMhRaffdeK$"
    "22b106c0f64c1d0896c8cce2641303613477dd5d7c24ad2d60e839b2f3f052c6129e7176"
    "fef5f7c1833bac4c15468d546c50c2db67ea93363aec1fddb663f95e"
)

# 過去に既定として配ったハッシュ。既定のまま運用されている管理者を「触られて
# いない」と判定するために残す（判定にだけ使い、新規投入には使わない）。
# 既定値を変えたら、直前の値をここへ積む。
SUPERSEDED_ADMIN_PASSWORD_HASHES: Sequence[str] = (
    # 平文 "admin"
    "scrypt:32768:8:1$kp58BgWIX2eGuqc6$"
    "879463f4b7684251a26d3ce6d863de80b756a47c42244709a752e0b935ad5f0b7392f598"
    "b9a43436d8af47aba78d78c726eb8fab983fe03e823c19f92108ff27",
)

__all__ = [
    "DEFAULT_ADMIN_DISPLAY_NAME",
    "DEFAULT_ADMIN_EMAIL",
    "DEFAULT_ADMIN_ID",
    "DEFAULT_ADMIN_PASSWORD",
    "DEFAULT_ADMIN_PASSWORD_HASH",
    "DEFAULT_ADMIN_ROLE",
    "DEFAULT_ADMIN_USERNAME",
    "PERMISSION_CODES",
    "ROLES",
    "ROLE_PERMISSIONS",
    "SUPERSEDED_ADMIN_PASSWORD_HASHES",
]
