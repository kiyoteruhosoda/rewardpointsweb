# identity_federation — 外部 IdP との連携（SSO）

OpenID Connect のクライアントとして、外部の IdP でログインさせるコンテキスト。

**利用者は作らない。** ここが行うのは「IdP が名乗った相手を、既にいる利用者へ
結び付ける」ところまでで、アカウントを増やす経路ではない（ADR-0029）。
パスワード・パスキーでのログインはこのコンテキストの外
（`presentation/fastapi/routers/auth.py` と `bounded_contexts/account_security`）。

## 構成

```
domain/          IdP の設定・クレームの対応付け・結び付きと控え、そして
                 永続化／外部処理のインターフェース（httpx / jwt には依存しない）
application/     ユースケース（送り出し・戻りの受け取り・券の引き換え）
infrastructure/  SQLAlchemy モデルとリポジトリ、httpx + PyJWT の実装
presentation/    API ルーター・スキーマ・依存の組み立て・起動時の確認
```

## 経路

| メソッド | 経路 | 用途 |
|---|---|---|
| GET | `/api/auth/sso/provider` | ボタンを出すか（未認証。接続先は返さない） |
| GET | `/api/auth/sso/login` | IdP へ送り出す（画面遷移） |
| GET | `/api/auth/sso/callback` | IdP からの戻り（画面遷移） |
| POST | `/api/auth/sso/token` | 引き換え券をトークンへ換える |

`/login` と `/callback` はブラウザの画面遷移で、応答本文を SPA は読めない。
失敗も JSON ではなくログイン画面への転送で返す（`?sso_error=<コード>`）。
表示文言はフロントエンドが決める。

## 誰としてログインするか

1. `(issuer, subject)` の結び付きがあれば、その利用者
2. 無ければ、**検証済みの**メールアドレスが一致する利用者へ結び付ける
3. どちらでもなければ断る（`sso_account_not_linked`）

`users.email` は任意項目なので、メールアドレスを持たない利用者（子ども）は
2 に当たらない。従来どおりパスワードかパスキーで入る。

一度結び付けば以後は 1 で決まるので、IdP 側でメールアドレスを変えても入れる。

## 往復のあいだに持つもの

| 表 | 何を持つか | 寿命 |
|---|---|---|
| `sso_login_sessions` | `state` / `nonce` / PKCE の検証値 / ブラウザの合言葉のハッシュ | `OIDC_LOGIN_SESSION_TTL_SECONDS` |
| `sso_login_tickets` | 引き換え券のハッシュと戻り先 | `OIDC_LOGIN_TICKET_TTL_SECONDS` |
| `federated_identities` | `(issuer, subject)` と利用者の結び付き | 恒久（利用者と一緒に消える） |

前の 2 つは 1 回限りで、消費は**削除の成否**で決める（同じ値を 2 本同時に
送られても 2 回通らない）。期限切れの行は発行のたびに掃除する。

プロセスのメモリではなく DB に置くのは、Gunicorn の複数ワーカー構成で送り出した
プロセスと戻り先のプロセスが一致しないため（パスキーのチャレンジと同じ理由）。

## 設定

キーは `OIDC_*`（`shared/kernel/settings/system_settings_defaults.py`）。
実際の値の入れ方は `docs/OPERATIONS.md`。

`OIDC_CLIENT_AUTH_METHOD` は 2 つ。

- `client_secret_basic` — `OIDC_CLIENT_SECRET` を使う
- `private_key_jwt` — `OIDC_PRIVATE_KEY_FILE` の秘密鍵で署名する。秘密がデプロイの
  変数にも DB にも載らない。**鍵ファイルはコンテナの実行ユーザーが読めること**
  （ディレクトリ自身にも通り抜けの権限が要る）

`OIDC_REDIRECT_URI` を空にすると `APP_BASE_URL` + `/api/auth/sso/callback` を使う。
IdP 側に登録した値と 1 文字でも違うと `invalid_client` になる。
