# OPERATIONS — 手順書

「〇〇したいとき、〇〇する」の操作手順のみを書く。設計の解説は
`ARCHITECTURE.md`、過去の経緯は `CHANGELOG.md` を参照。

## ローカル開発を始めたいとき

```bash
uv sync                          # 依存関係をインストール
uv run python main.py            # 開発サーバー起動（SQLite: app.db）
```

- API: http://127.0.0.1:8000 / Swagger UI: http://127.0.0.1:8000/docs
- 初回はマイグレーションとマスタデータ投入を行う:

```bash
uv run alembic upgrade head
uv run python scripts/seed_master_data.py
```

- 初期管理者: ログイン ID `admin@example.com` / パスワード `admin@example.com`
  （`ADMIN_INITIAL_PASSWORD` 環境変数で上書き可。本番では必ず変更する）

ログインの識別子は **ユーザー名**（`users.username`）。メールアドレスは任意項目で、
持たないアカウント（子ども）も作れる（ADR-0011）。既存アカウントの移行では
`username` にメールアドレスの値が入るため、これまでと同じ文字列でログインできる。

## フロントエンドを開発したいとき

```bash
cd frontend
npm install
npm run dev        # http://localhost:5173（/api は 8000 へプロキシ）
```

ビルドして FastAPI から配信させたいとき:

```bash
cd frontend && npm run build     # frontend/dist に出力 → / で配信される
```

## テストを実行したいとき

```bash
uv run pytest                    # smtp マーカーは既定で除外
cd frontend && npm run test      # Vitest
```

## 品質ゲートを手元で確認したいとき

CI と同じ順序・同じコマンドを流す。落ちたらマージできない（ADR-0006）。

```bash
make check                       # Backend + Frontend を全部
make check-backend               # Backend だけ
make check-frontend              # Frontend だけ
```

`make check` の中身:

```bash
# Backend
uv run ruff format --check .     # 整形
uv run ruff check .              # 静的解析
uv run ruff check --preview --select PLR1702,PLR0917 .  # ネスト深度・位置引数（ADR-0016）
uv run mypy                      # 型チェック（対象は pyproject.toml の files）
uv run pytest                    # テスト

# Frontend（cd frontend）
npm run format:check             # 整形（Prettier）
npm run lint                     # 静的解析（ESLint）
npm run type-check               # 型チェック（tsc --noEmit）
npm run test                     # テスト（Vitest）
```

個別に回したいときは `make lint` / `make typecheck` / `make test`、
Frontend は `make lint-frontend` / `make typecheck-frontend` / `make test-frontend`。

## 整形の指摘を自動で直したいとき

```bash
make format                      # Backend + Frontend を自動整形
make format-backend              # ruff format . && ruff check . --fix
make format-frontend             # prettier --write .
```

`ruff check --fix` と `eslint --fix` で直らない指摘は手で直す。

## フロントエンドのテストを書きたいとき

`frontend/src/**/*.test.ts` / `*.test.tsx` に置く（`vite.config.ts` の
`test.include`）。jsdom + Testing Library が使える。

```bash
cd frontend
npm run test:watch               # 変更を監視して再実行
npm run test:coverage            # カバレッジ（coverage/ に出力）
```

## マイグレーションを追加したいとき

1. `shared/infrastructure/models/` のモデルを変更する。
2. マイグレーションを生成・編集する:

```bash
uv run alembic revision --autogenerate -m "<description>"
```

3. 生成ファイル先頭に `from __future__ import annotations` を入れ、
   `upgrade()` / `downgrade()` 双方を確認する。
4. `uv run alembic upgrade head` で適用し、テストで整合性を確認する。

## 設定キーを追加したいとき

以下の3ファイルすべてを更新する（CLAUDE.md「設定管理」参照）:

1. `shared/kernel/settings/system_settings_defaults.py`
2. `shared/kernel/settings/settings.py`
3. `presentation/fastapi/admin/system_settings_definitions.py`

## Docker イメージをビルドしたいとき

```bash
./scripts/build.sh   # アプリ + DB イメージ → dist/（tar・deploy.sh・manifest 一式）
# make build でも同じ（scripts/build.sh を呼ぶだけ）
```

## docker compose でローカル起動したいとき

リポジトリのルートで実行する。`.env` は必須ではなく、無ければ
`docker-compose.yml` の既定値（開発向け）で起動する。

```bash
docker compose up -d --build     # db / web / nginx が起動（初回はイメージをビルド）
docker compose logs -f web       # 起動の様子を見る
docker compose down              # 停止（データは mnt/ に残る）
```

- アプリ: http://127.0.0.1:8080 （nginx 経由）
- 初回は web / db のイメージをビルドするため数分かかる。2 回目以降は `--build` を
  外せば既存のイメージを使う。
- コンテナ・ネットワーク・イメージの名前は `rewardpointsweb` で固定される
  （compose プロジェクト名は `docker-compose.yml` の `name:`）。clone 先の
  ディレクトリ名には依存しない。
- 設定を変えたいときは `cp .env.example .env` して編集する。公開する環境では
  DB 資格情報・`JWT_SECRET_KEY` などを必ず上書きすること。
- 永続データはホストの `mnt/`（`HOST_DATA_ROOT`）。消すと DB は初期化される。

ビルドと「`.env` を任意にする」を担うのは `docker-compose.override.yml`（`-f` を
付けずに実行したときだけ自動で読まれる）。配置先の `deploy.sh` は
`-f docker-compose.yml` を明示するため、そちらはロード済みイメージをそのまま使い、
`.env`（`deploy.sh` が自動生成する）も従来どおり必須のまま。この分け方は
`env_file` の `required:` が Compose 2.24.0 以降の機能で、配置先の Compose が
それより古いことがあるため。

## DB に直接つなぎたいとき

DB はホストにポートを持たない（同じ Docker ネットワークの中からしか到達できない）。
保守はコンテナの中で行う。パスワードはコンテナ内の環境変数を使い、コマンド行にも
シェル履歴にも残さない（`sh -c` に `'` シングルクォートで渡す）。

```bash
# 対話シェル（アプリ用ユーザー）
docker compose exec db sh -c 'mysql -u"$MARIADB_USER" -p"$MARIADB_PASSWORD" "$MARIADB_DATABASE"'

# 1 文だけ実行する
docker compose exec db sh -c 'mysql -u"$MARIADB_USER" -p"$MARIADB_PASSWORD" "$MARIADB_DATABASE" -e "SHOW TABLES;"'
```

ダンプ・リストア（`-T` を付けて標準入出力をそのまま繋ぐ）:

```bash
docker compose exec -T db sh -c 'mysqldump -u root -p"$MARIADB_ROOT_PASSWORD" "$MARIADB_DATABASE"' > dump.sql
docker compose exec -T db sh -c 'mysql -u root -p"$MARIADB_ROOT_PASSWORD" "$MARIADB_DATABASE"' < dump.sql
```

別のコンテナからつなぎたいときは、同じネットワーク（`.env` の
`DOCKER_NETWORK_NAME`。既定は `rewardpointsweb`）に参加させ、ホスト名 `db`・
ポート 3306 を指す:

```bash
docker run --rm -it --network rewardpointsweb mariadb:10.11 \
  mysql -h db -u web_user -p appdb
```

## 管理者のパスワードが分からなくなったとき

初期管理者（ログイン ID `admin@example.com`）のパスワードを再設定する。メールが
使えない環境でも復旧できるよう、サーバー側から直接戻す経路を用意してある。

```bash
# 既定値（admin@example.com）へ戻す
docker compose exec web python scripts/seed_master_data.py --reset-admin-password

# 好きなパスワードにする
docker compose exec -e ADMIN_INITIAL_PASSWORD='新しいパスワード' web \
  python scripts/seed_master_data.py --reset-admin-password
```

`--reset-admin-password` を付けないとパスワードは変わらない（投入は冪等で、
運用者が決めたパスワードを黙って壊さないため）。

## ログインが「サーバー側でエラーが発生しました」になるとき

パスワード違いなら「メールアドレスまたはパスワードが正しくありません」が出る。
この文言はサーバー側の例外（HTTP 500）なので、原因はログにある。画面の応答
ヘッダー `X-Request-Id` と同じ `requestId` で該当行を引く。

```bash
docker compose logs web | grep unhandled_exception     # traceback つきで出る
```

DB の `log` テーブルにも同じ行が入る（`trace` 列に traceback）。

## デプロイしたいとき

配置先サーバーの `<アプリ名>/<stg|prod>/` に `dist/` の中身をそのまま置いて実行する:

```bash
./deploy.sh app          # 通常デプロイ（アプリのみ更新）
./deploy.sh migrate      # DDL 更新時（Alembic migration 追加時）
./deploy.sh reset        # 完全初期化（DB 消去。破壊的）
```

**置き場所がデプロイの名前を決める。** アプリ名は親ディレクトリ名、環境（stg / prod）は
自分のディレクトリ名から自動判定される。

```
/volume1/docker/rewardpointsweb/prod/deploy.sh   → アプリ名 rewardpointsweb・環境 prod
/volume1/docker/kaimono/stg/deploy.sh            → アプリ名 kaimono・環境 stg
```

イメージタグ・compose プロジェクト名・DB コンテナ名・ネットワーク名はすべてアプリ名から
作られるので、**別のアプリは別のディレクトリへ置けばそれだけで衝突しない**。同じホストで
複数のアプリを動かすときに気にすることは無い。

ディレクトリ名を使えないとき（記号だけの名前など）だけ `.env` の `APP_NAME` で明示する。
どの名前が使われたかは起動時のログ 1 行目付近に出る。

`.env` が無ければ初回実行時にテンプレートが自動生成される。

**ディレクトリ名を変えたとき**は、旧ディレクトリで起動したコンテナが旧名のまま残る。
`deploy.sh` は「その配置から起動したと確認できるコンテナだけ」を畳んで新しい名前へ
移すので、通常はそのままデプロイし直せばよい（データはホスト側の `mnt/` にある）。

## アプリのアイコンを変えたいとき

`scripts/generate_app_icons.py` の定数を直して実行し、生成された 5 ファイルを
コミットしてからデプロイする（詳細は `scripts/README.md`）。

```bash
uv run python scripts/generate_app_icons.py
```

参照 URL に付く版はビルド時に画像の中身から決まるので、手で書き換える箇所は無い。

デプロイ後の反映は開き方で変わる。

| 開き方 | 反映 |
|---|---|
| ブラウザのタブ（favicon） | 再読み込みで変わる |
| Android にインストールした PWA | Chrome が manifest の変更に気づいてから。即座ではなく、最大 1 日ほどかかる |
| iOS にインストールした PWA | **変わらない。** ホーム画面から削除し、追加し直す |

iOS はホーム画面に追加した時点のアイコンを端末に焼き付けるため、配信側で
できることは無い。急ぐ場合は追加し直してもらう。

## デプロイが `network ... is ambiguous` で失敗したとき

同じ名前の Docker ネットワークが 2 つ以上できている。`deploy.sh` は起動前と
失敗時に自動で掃除するので、まずはもう一度デプロイし直す。

```bash
./deploy.sh app
```

**「containers outside this project are attached」で止まったとき**は、そのネットワークに
このアプリ以外のコンテナ（保守用に繋いだ mysql クライアント等）が接続している。
自動では触らないので、表示されたコンテナを停止するか別のネットワークへ移してから
デプロイし直す。

それでも「Could not resolve the duplicated Docker network」で止まるときは手で消す
（ネットワークは作り直せる。消しても DB・アプリのデータには影響しない）:

```bash
docker network ls | grep rewardpointsweb      # 同名で ID が違う行を確認する
docker network rm <ID> <ID>                   # 1 つ残して他を削除する
./deploy.sh app                               # 残った 1 つを compose が再利用する
```

コンテナが接続中で消せないときは、先に切り離す:

```bash
docker network inspect <ID>                   # Containers に出るコンテナ名を確認
docker network disconnect -f <ID> <コンテナ名>
```

## デプロイ先に git が無いホスト（Synology 等）で一括デプロイしたいとき

`scripts/build-remote-container.sh` をデプロイ先の `<app>/<stg|prod>/` に一度だけ手で置き、
同じ場所に `build-remote-container.env`（雛形: `scripts/build-remote-container.env.example`）を
作成してから実行する:

```bash
./build-remote-container.sh            # app（通常デプロイ）
./build-remote-container.sh migrate
./build-remote-container.sh reset
```

git pull → build.sh → dist/ 取り込み → deploy.sh を 1 本で実行する
（ビルドは同一ホスト上の dev コンテナ内。スクリプト自身も自動で最新版へ差し替わる）。

## システム設定を変更したいとき

管理画面（`/admin/config`。要 `admin:system-settings` 権限）から編集する。
保存すると即時反映される（環境変数が設定されているキーは環境変数が優先）。

「再起動後に反映」と表示される項目（ログ設定・CORS）は保存だけでは効かない。
保存後に出る「今すぐ再起動」を押す（要 `system:manage` 権限）。要求は DB に置かれ、
最大 10 秒でアプリが自分を終了し、コンテナの restart policy で復帰する。

## アプリを再起動したいとき

- 画面: `/admin/config` の再起動ボタン、または `POST /api/admin/system/restart`
- ホスト: `docker compose restart web`

## 二要素認証・パスキーを設定したいとき

利用者自身が `/security`（プロフィール → セキュリティ）から操作する。

- 二要素認証: 「設定する」→ 認証アプリで QR を読む → 表示されたコードを入力して確定。
  確定するまで有効にならないため、途中でやめてもログインできなくなることはない。
- パスキー: 「パスキーを追加」→ 端末の画面ロック／セキュリティキーで承認。

パスキーを使う前に `WEBAUTHN_RP_ID` / `WEBAUTHN_ORIGIN` を実際に開く URL へ合わせる
（`.env.example` 参照）。RP ID を後から変えると登録済みのパスキーは使えなくなる。

| 開き方 | `WEBAUTHN_RP_ID` | `WEBAUTHN_ORIGIN` |
|---|---|---|
| `npm run dev`（既定） | `localhost` | `http://localhost:5173` |
| ビルド済み SPA を FastAPI から | `localhost` | `http://localhost:8000` |
| docker compose（nginx 経由） | `localhost` | `http://localhost:8080` |
| 本番 | 公開ドメイン | `https://<公開ドメイン>` |

RP ID にはドメイン名しか指定できない（IP アドレス・ポート番号・URL は不可）。開発時は
`127.0.0.1` ではなく `localhost` で開くこと。RP 名（`WEBAUTHN_RP_NAME`）は画面に出す
表示名で、RP ID とは別物——同じ値を入れないこと。

`WEBAUTHN_ORIGIN` は `scheme://ホスト[:ポート]` の形だけを受け付ける。パス・クエリ・
`user:pass@` の付いた URL は、ブラウザが送るオリジンと一致しないため使えない。既定
ポート（`:443` / `:80`）は書いても無視する。

RP ID がオリジンのドメイン（またはその上位ドメイン）になっていない組み合わせは
`/admin/config` が保存を拒む。環境変数で固定してしまった場合は画面から直せないため、
パスキーの発行が `passkey_misconfigured` 系のエラーになる。`.env` を直して再起動する。

## ログを確認したいとき

- 画面: `/admin/logs`（要 `system:manage` 権限）
- DB: `log` テーブル（`requestId` でリクエスト単位に追跡）
- コンテナ: `docker compose logs web`

エラーだけを見たいときはレベルで絞る（**5xx は ERROR、4xx は WARNING**、401 は
INFO。ログインの失敗は WARNING）。失敗した行の本文にはエラーコードが入る
（`request_failed: user_not_found`）。

管理操作は本文の頭で引ける。`admin_user_created` / `admin_user_updated` /
`admin_user_deleted` / `admin_role_created` / `admin_role_updated` /
`admin_role_deleted` / `system_settings_updated` / `login_failed`。

`/healthz`・`/readyz`・`/api/health`・`/metrics` の成功したアクセスは記録されない
（失敗したときは記録される）。死活の確認は `docker compose ps` の healthcheck 状態か
`/metrics` を見る。

## 子どもがパスワードを忘れたとき

子アカウントはメールアドレスを持たないため、リセットリンクを送れない。親
（`owner` / `parent`）が画面から一時パスワードを発行する。

なお「パスワードを忘れた場合」の画面はユーザー名で申し込む。メールアドレスを設定して
いないアカウントには、その場で「親に頼んでください」と表示される。

1. 「家族」→ 対象の家族を開く
2. 子どもの行の「一時パスワードを発行」を押す
3. 画面に出たパスワードを本人へ伝える（表示されるのはこの 1 度だけ）

子は一時パスワードでログインしたあと、新しいパスワードを決めるまで他の画面へ
進めない。発行の事実（発行者・対象・日時）は `log` テーブルに残る。

有効期限は `TEMPORARY_PASSWORD_TTL_SECONDS`（既定 24 時間）。切れた場合は発行し直す。

## 子どもに自分の端末からログインさせたいとき

子アカウントは子ども自身では作れない。親が用意して招待コードを渡す。1 と 3 は
`owner` / `parent` のどちらでもよいが、**招待コードの発行（2）は `owner` だけ**。

1. 「家族」→ 対象の家族を開き、「子どもを追加」で名前を登録する
   （この時点でポイント台帳ができる。アカウントはまだ無い）
2. 「招待」の「〇〇 の招待コード」を押し、表示されたコードを控える
   （表示されるのはこの 1 度だけ。失くしたら発行し直す）
3. 子どもの端末で `/join` を開き、コード・ユーザー名・パスワードを入力する

有効期限は `FAMILY_INVITATION_TTL_SECONDS`（既定 7 日）。

もう 1 人の親を家族へ加える場合は「もう 1 人の親を招待」でコードを発行し、
相手がログインした状態で「家族」→「コードで参加する」から入力する。

## 毎日おなじポイントを自動で足したいとき

子ごとに「毎日いくつ足すか」を決めておくと、日付が変わるたびにサーバーが台帳へ
1 行足す（ADR-0024）。手で記録する必要はない。

1. 「家族」→ 対象の子どもの台帳を開く
2. 「まいにちのボーナス」に 1 日あたりのポイントと、履歴に出す文言を入れる
3. 「まいにちのボーナスをはじめる」を押す

決めた時点では台帳は動かない。最初の 1 行が入るのは次に日付が変わったとき。
やめるときは同じ場所の「やめる」を押す（すでに足したポイントは履歴に残る）。

日付の区切りは `DAILY_BONUS_TIME_ZONE`（既定 `UTC`）。日本時間の 0 時で切りたい
場合は管理画面のシステム設定で `Asia/Tokyo` にする。アプリが止まっていた日は
次の起動でまとめて足される（遡る上限は `DAILY_BONUS_MAX_CATCH_UP_DAYS`、既定 31 日）。
