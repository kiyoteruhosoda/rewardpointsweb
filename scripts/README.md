# scripts — 現在の仕様

| スクリプト | 役割 |
|---|---|
| `entrypoint.sh` | コンテナ起動。起動診断 → DB 接続待ち（MariaDB 使用時）→ `web` モードでは `alembic upgrade head` の後に Gunicorn + UvicornWorker を起動する。モードは compose の `command`（`web` / `migrate`）で指定する。 |
| `run_db_migrations.py` | `alembic upgrade head` を実行する。entrypoint / deploy から共用。どこから呼んでもプロジェクトルートへ chdir して動く。 |
| `seed_master_data.py` | ロール・権限・初期管理者を投入する（冪等）。値の正本は `shared/domain/auth/master_data.py`。`ADMIN_INITIAL_PASSWORD` 環境変数で初期管理者パスワードを上書きできる。 |
| `generate_app_icons.py` | アプリアイコン（`frontend/public/` の `favicon.svg`・`pwa-*.png`・`apple-touch-icon.png`）を書き出す。SVG と PNG を同じ座標から作るため、形は必ず一致する。図柄・色を変えるときはこのスクリプトを直して実行し、生成された 5 ファイルをコミットする（`favicon.svg` を手で編集しても PNG は追随しない）。 |
| `generate_version.sh` | `shared/kernel/version.json` を Git 情報から生成する（ローカル確認用。Docker ビルドでは Dockerfile の ARG から生成される）。 |
| `build.sh` | ソース側でのビルド。アプリ + DB イメージをビルドし、`dist/` にデプロイバンドル（`image.tar`・`image-db.tar`・`deploy.sh`・`.env.example`・`manifest.env`・`manifest.sha256`）を書き出す。`make build` はこれを呼ぶだけ。`PLATFORM=linux/amd64` でクロスビルド（要 buildx）。 |
| `deploy.sh` | 配置先サーバーでのデプロイ。配置ディレクトリ名（`stg` / `prod` 系）から環境を自動判定し、`app` / `migrate` / `reset` の3モードを持つ。`.env` が無ければテンプレートを自動生成する。compose と nginx 設定はロードしたイメージ内のコピーへ常に同期される。 |
| `build-remote-container.sh` | git 非搭載のデプロイ先向けの一括デプロイ（SYNC → BUILD → PICK → DEPLOY）。同一ホスト上の dev コンテナ内で git pull と `build.sh` を実行し、生成された `dist/` をデプロイ先へ取り込んで `deploy.sh` を実行する。手置きのブートストラップだが、実行のたびに dev コンテナ内の最新版と比較して自分自身を自動更新する。設定はスクリプトと同じ場所の `build-remote-container.env`（雛形: `build-remote-container.env.example`）。 |

## deploy.sh の挙動

- 配置は `dist/` の中身をそのまま `<app>/<stg|prod>/` へ展開した形のみ
  （`deploy.sh` が環境ディレクトリ直下にある前提で動く）。
- イメージは `image.tar`（`scripts/build.sh` の成果物）を `docker load` し、
  環境別タグ（`fastapitemplate:stg` 等）を付け直す。stg / prod を同一ホストで
  運用してもイメージを取り合わない。
- `manifest.env` / `manifest.sha256` があれば、tar の checksum 検証（転送破損検出）と
  ロード済みイメージ ID の照合（一致すれば `docker load` を省略）を行う。無ければ
  従来どおり動く。
- `reset` は `mnt/db_data` と `mnt/data` を削除する破壊的操作。DB イメージ
  （`image-db.tar`）もこのとき再ロードされる。
- 停止（`docker compose down`）が失敗したときは、プロジェクトのコンテナを
  `docker rm -f` してからもう一度 `down` する。ネットワークを残したまま次へ進まない。
- 起動前に `.env` の `DOCKER_NETWORK_NAME`（既定は `fastapitemplate`。`.env` を自動生成
  する初回は生成後の値を見る）と同名の Docker ネットワークが 2 つ以上ないかを見る。
  あれば全部削除して compose に 1 つだけ作り直させる（ネットワークは永続データを
  持たないため消して差し支えない）。起動が `network ... is ambiguous` で失敗した場合も、
  同じ掃除をして 1 度だけ再試行する。
- ただし、そのネットワークにこのプロジェクト以外のコンテナ
  （`com.docker.compose.project` ラベルが一致しないもの）が繋がっているときは何もしない。
  切り離すとそのコンテナは動いたまま通信できなくなり、`up` でも復旧しないため、
  該当コンテナ名を出して終了する。重複が残るときも手で消すよう促して終了する。
- ヘルスチェックは `http://127.0.0.1:<WEB_HOST_PORT>/healthz`。失敗時は
  各コンテナのログを出力して終了する。
