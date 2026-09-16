# identity_federation — 外部 IdP との連携（SSO）

OpenID Connect のクライアントとして、外部の IdP でログインさせるコンテキスト。

**IdP が名乗った相手を、このアプリの利用者へ結び付ける。** 初めての相手には口座を
作る（ADR-0041）。誰に作ってよいかは IdP（assay）のアプリの割り当てが決めていて、
割り当てが無い人は assay の画面で止まり、ここまで戻ってこない。
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
   （`OIDC_LINK_BY_EMAIL`。⚠ 既定は寄せない。ADR-0033）
3. どちらでもなければ**口座を作って**結び付ける（ADR-0041）。親（`member`）・家族なし・
   パスワードなし。`username` は IdP の `preferred_username`

⚠ **作れないときは断る。**

- 同じメールアドレスの口座が既にある（2 で寄せなかった）→ `sso_account_not_linked`。
  口座を 2 つにしない。本人がその口座へ入って設定画面から結び付ける（ADR-0036）
- `preferred_username` が無い・識別子の規則に合わない・既に使われている →
  `sso_username_unavailable`。⚠ 連番を付けない

`users.email` は任意項目なので、メールアドレスを持たない利用者（子ども）は
2 に当たらない。従来どおりパスワードかパスキーで入る。

一度結び付けば以後は 1 で決まるので、IdP 側でメールアドレスを変えても入れる。
**メールアドレスのクレームが来なくても入れる**（ADR-0038）——要るのは 2 の
ときだけで、3 で作る口座もメールアドレス無しで作れる。

**1 で決まった利用者は、写しを毎回書き直す**（ADR-0038）。IdP が正で、こちらが
持っている `email` と `display_name` は表示のための複製でしかない。⚠ **他の利用者と
ぶつかる値は書かない**（`users.email` は一意）。⚠ **`username`（ログインの識別子）は
触らない。**

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

`OIDC_ACR_VALUES` は**要求する認証の強度**（空 = 要求しない。既定）。⚠ **入れたら
fail closed** ——戻ってきた `acr` が要求と一致しなければ、**返ってこない場合も**
断る（ADR-0039）。
