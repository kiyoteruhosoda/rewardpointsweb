# scripts — 現在の仕様

| スクリプト | 役割 |
|---|---|
| `entrypoint.sh` | コンテナ起動。起動診断 → DB 接続待ち（MariaDB 使用時）→ `web` モードでは `alembic upgrade head` の後に Gunicorn + UvicornWorker を起動する。モードは compose の `command`（`web` / `migrate`）で指定する。 |
| `run_db_migrations.py` | `alembic upgrade head` を実行する。entrypoint から使う。どこから呼んでもプロジェクトルートへ chdir して動く。 |
| `seed_master_data.py` | ロール・権限・初期管理者を投入する（冪等）。値の正本は `shared/domain/auth/master_data.py`。`ADMIN_INITIAL_PASSWORD` 環境変数で初期管理者パスワードを上書きできる。既存の管理者のパスワードは変えないが、`--reset-admin-password` を付けたときだけ戻す（締め出されたときの復旧経路）。 |
| `generate_app_icons.py` | アプリアイコン（`frontend/public/` の `favicon.svg`・`pwa-*.png`・`apple-touch-icon.png`）を書き出す。SVG と PNG を同じ座標から作るため、形は必ず一致する。図柄・色を変えるときはこのスクリプトを直して実行し、生成された 5 ファイルをコミットする（`favicon.svg` を手で編集しても PNG は追随しない）。 |
| `generate_version.sh` | `shared/kernel/version.json` を作る。**ビルドの前に**走らせる（build の「版を刻む」段（`pre_build`）／`make image`）。優先順位は git > 既にある version.json > dev で、イメージの中（git が無い）では既存を上書きしない（ADR-0028）。 |

