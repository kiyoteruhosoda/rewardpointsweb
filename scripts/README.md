# scripts — 現在の仕様

| スクリプト | 役割 |
|---|---|
| `entrypoint.sh` | コンテナ起動。起動診断 → DB 接続待ち（MariaDB 使用時）→ `web` モードでは `alembic upgrade head` の後に Gunicorn + UvicornWorker を起動する。モードは compose の `command`（`web` / `migrate`）で指定する。 |
| `run_db_migrations.py` | `alembic upgrade head` を実行する。entrypoint / deploy から共用。どこから呼んでもプロジェクトルートへ chdir して動く。 |
| `seed_master_data.py` | ロール・権限・初期管理者を投入する（冪等）。値の正本は `shared/domain/auth/master_data.py`。`ADMIN_INITIAL_PASSWORD` 環境変数で初期管理者パスワードを上書きできる。既存の管理者のパスワードは変えないが、`--reset-admin-password` を付けたときだけ戻す（締め出されたときの復旧経路）。 |
| `generate_app_icons.py` | アプリアイコン（`frontend/public/` の `favicon.svg`・`pwa-*.png`・`apple-touch-icon.png`）を書き出す。SVG と PNG を同じ座標から作るため、形は必ず一致する。図柄・色を変えるときはこのスクリプトを直して実行し、生成された 5 ファイルをコミットする（`favicon.svg` を手で編集しても PNG は追随しない）。 |
| `generate_version.sh` | `shared/kernel/version.json` を Git 情報から生成する（ローカル確認用。Docker ビルドでは Dockerfile の ARG から生成される）。 |
| `build.sh` | ソース側でのビルド。アプリ + DB イメージをビルドし、`dist/` にデプロイバンドル（`image.tar`・`image-db.tar`・`deploy.sh`・`.env.example`・`manifest.env`・`manifest.sha256`）を書き出す。`make build` はこれを呼ぶだけ。`PLATFORM=linux/amd64` でクロスビルド（要 buildx）。 |
| `deploy.sh` | 配置先サーバーでのデプロイ。配置ディレクトリ名（`stg` / `prod` 系）から環境を自動判定し、`app` / `migrate` / `reset` の3モードを持つ。`.env` が無ければテンプレートを自動生成する。compose と nginx 設定はロードしたイメージ内のコピーへ常に同期される。 |
| `build-remote-container.sh` | git 非搭載のデプロイ先向けの一括デプロイ（SYNC → BUILD → PICK → DEPLOY）。同一ホスト上の dev コンテナ内で git pull と `build.sh` を実行し、生成された `dist/` をデプロイ先へ取り込んで `deploy.sh` を実行する。手置きのブートストラップだが、実行のたびに dev コンテナ内の最新版と比較して自分自身を自動更新する。設定はスクリプトと同じ場所の `build-remote-container.env`（雛形: `build-remote-container.env.example`）。 |

## deploy.sh の挙動

- 配置は `dist/` の中身をそのまま `<app>/<stg|prod>/` へ展開した形のみ
  （`deploy.sh` が環境ディレクトリ直下にある前提で動く）。
- イメージは `image.tar`（`scripts/build.sh` の成果物）を `docker load` し、
  環境別タグ（`rewardpointsweb:stg` 等）を付け直す。stg / prod を同一ホストで
  運用してもイメージを取り合わない。
- **配置場所がデプロイの名前を決める。** アプリ名は親ディレクトリ名、環境は自分の
  ディレクトリ名から取る（`<アプリ名>/<stg|prod>/deploy.sh`）。イメージタグ・compose
  プロジェクト名・DB コンテナ名・ネットワーク名はすべてそこから導くため、別のアプリを
  別のディレクトリへ置けば名前は構造的に衝突しない。スクリプトにアプリ名を焼き込むと、
  同じ名前を使う別アプリと `container_name` やホストポートを奪い合う。
- アプリ名の優先順位は `.env` の `APP_NAME` > 親ディレクトリ名 > `BUILD_APP_NAME`。
  ディレクトリ名は docker の識別子として使うため、小文字英数と `-` `_` へ正規化する
  （`RewardPoints Web` → `rewardpoints-web`）。正規化しても空になるときだけ
  `BUILD_APP_NAME` へ落ちる。実際に使われた名前と出所は起動時に 1 行で出す。
  ただし解決結果が `LEGACY_APP_NAMES` の旧名に当たったときは、出所によらず採用せず
  `BUILD_APP_NAME` を使う（引退した名前でコンテナを作り続けないため）。配置ディレクトリ
  が旧名のままでも、旧名の頃に生成された `.env` の `APP_NAME` が残っていても移行する。
- `BUILD_APP_NAME` は「デプロイの名前」ではなく「`image.tar` の中身がどう tag されて
  いるか」。`manifest.env` が無いときの load 後の参照先にだけ使う（あればそちらの
  `app_ref` / `db_ref` が正）。配置ディレクトリを変えても tar の中身は変わらない。
- `LEGACY_APP_NAMES` に挙げた旧アプリ名（`fastapitemplate`）で動いているコンテナが
  あれば、旧名の compose プロジェクトを一度だけ `down` してから新しい名前で起動し直す。
  ただし down するのは、compose の `com.docker.compose.project.working_dir` ラベルが
  この環境ディレクトリと一致するコンテナだけで構成されているときに限る。プロジェクト名
  ラベルの絞り込みは docker デーモン全体を見るため、それだけを根拠にすると同じ名前を
  使う**別のアプリ**を停止・削除してしまう。他所のコンテナが 1 つでも混ざっていたら
  何もせず、コンテナ名を出して人に委ねる。
  ただし**この配置自身が旧名から移行してきた場合**（配置ディレクトリや `.env` が旧名
  だった場合）は、触らずに続行せずデプロイを中止する。旧名のコンテナはこの配置の前身
  である可能性が高く、畳めないまま `up` へ進むと新旧 2 つの MariaDB が同じ
  `HOST_DATA_ROOT/db_data` を同時に開くため。`container_name` もネットワーク名も新旧で
  異なるので衝突では止まらず、止まるのは後段の nginx がホストポートを取れないときで、
  そのときには既に DB が壊れている。
  併せて、自動生成した `.env` の `DB_CONTAINER_NAME` / `DOCKER_NETWORK_NAME` が旧既定値
  のままなら新しい名前へ書き換える（運用者が独自に決めた値には触れない）。永続データは
  ホスト側の `HOST_DATA_ROOT` にあるため、この入れ替えで消えない。
- `manifest.env` / `manifest.sha256` があれば、tar の checksum 検証（転送破損検出）と
  ロード済みイメージ ID の照合（一致すれば `docker load` を省略）を行う。無ければ
  従来どおり動く。
- `reset` は `mnt/db_data` と `mnt/data` を削除する破壊的操作。DB イメージ
  （`image-db.tar`）もこのとき再ロードされる。
- 停止（`docker compose down`）が失敗したときは、プロジェクトのコンテナを
  `docker rm -f` してからもう一度 `down` する。ネットワークを残したまま次へ進まない。
- 起動前に `.env` の `DOCKER_NETWORK_NAME`（既定は `rewardpointsweb`。`.env` を自動生成
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
