#!/bin/bash
# デプロイスクリプト（stg / prod 共通・配置ディレクトリからアプリ名と環境を自動判定）
#
# **このスクリプトの置き場所が、デプロイの名前を決める。**
# アプリ名は親ディレクトリ名、環境は自分のディレクトリ名から取る。イメージタグ・
# compose プロジェクト名・DB コンテナ名・ネットワーク名はすべてそこから導くため、
# 別のアプリを別のディレクトリへ置けば、名前は構造的に衝突しない（スクリプトに
# アプリ名を焼き込むと、同じ名前を使う別アプリと container_name やホストポートを
# 奪い合う）。ディレクトリ名を使えないときだけ .env の APP_NAME で上書きする。
# ただし LEGACY_APP_NAMES の旧名だけは、どの出所から来ても採用しない（引退した名前を
# 名乗り続けないため。旧名の配置ディレクトリのままでも新しい名前へ移行する）。
#
# 配置想定（環境ごとに自己完結したディレクトリ。<app>/ 配下に stg/ と prod/ を置き、
# scripts/build.sh が出力した dist/ の中身をそのまま展開する）:
#   <app>/                   # ← このディレクトリ名がアプリ名になる
#     stg/                   # ← このディレクトリ名が環境になる
#       image.tar          # ビルド済みアプリイメージ
#       image-db.tar       # DB イメージ（reset 時のみ使用）
#       deploy.sh          # このスクリプト（dist/deploy.sh を配置）
#       manifest.env       # ビルドメタデータ（commit・イメージ ID）
#       manifest.sha256    # tar の checksum（配置時の転送破損検出）
#       .env               # stg 用設定（無ければ初回デプロイ時にテンプレートを自動生成）
#       docker-compose.yml # stg 用（デプロイ時にイメージ内のコピーで自動更新される）
#       mnt/               # コンテナマウント用データ（data/ と db_data/ が作られる）
#     prod/                # 上記と同じ構成
#
# 使い方（モード引数は必須。<app>/<stg|prod>/ で実行する）:
#   ./deploy.sh app      # 通常デプロイ（アプリのみ更新。DBスキーマ変更なし）
#   ./deploy.sh migrate  # DDL更新時（新しい Alembic migration を追加した場合）
#   ./deploy.sh reset    # 完全初期化（DB・データ消去。破壊的）
#
# デプロイ中にエラーが発生した場合は、失敗したモジュール（コンテナ）のログを
# 出力して終了する。

set -Eeuo pipefail

# scripts/build.sh がイメージに付けるタグ名。デプロイの名前ではなく「tar の中身が
# 何という名前で tag されているか」で、manifest.env が無いときの load 後の参照先に
# だけ使う（manifest.env があればそちらの app_ref / db_ref が正）。
BUILD_APP_NAME="rewardpointsweb"

# 以前このアプリが名乗っていた名前。旧名で起動中のコンテナは「別プロジェクトの
# 残骸」として残り、同じ container_name / ホストポートを奪い合って次の up を
# 失敗させる。一度だけ旧名で down を通し、.env に焼き付いた旧名も新名へ移す
# （下記 take_down_legacy_projects / migrate_legacy_env_names）。
# 永続データはホスト側の $HOST_DATA_ROOT にあるので、この入れ替えで消えない。
LEGACY_APP_NAMES="fastapitemplate"

# 配置は dist/ をそのまま展開した形（<app>/<env>/deploy.sh）のみ。環境ディレクトリ直下で動く。
BASE_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ENV_NAME="$(basename "$BASE_DIR")"
ENV_FILE="$BASE_DIR/.env"

# ===== ログ =====
# TAG は ENV_NAME にしか依存しない。アプリ名の解決でも警告を出すため、
# それより前に定義しておく。
TAG="[deploy:$ENV_NAME]"
log()  { echo -e "\033[36m${TAG}\033[0m $*"; }
warn() { echo -e "\033[33m${TAG}[warn]\033[0m $*" >&2; }
err()  { echo -e "\033[31m${TAG}[error]\033[0m $*" >&2; }

# ===== .env の値を読む（compose interpolation と同じく「最後の定義」を採用） =====
# CR と前後の空白は必ず除去する（CR が残るとバインドマウント失敗の原因になる）。
# APP_NAME の解決で使うため、他のパス定義より先に置く。
env_file_value() {
  local key="$1"
  [ -f "$ENV_FILE" ] || return 0
  grep -E "^${key}=" "$ENV_FILE" 2>/dev/null | tail -n1 | cut -d'=' -f2- \
    | tr -d '\r' | sed -e 's/^[[:space:]]*//' -e 's/[[:space:]]*$//' || true
}

# ===== アプリ名の決定（.env の APP_NAME > 親ディレクトリ名 > ビルド時の名前） =====
# ただし LEGACY_APP_NAMES に挙げた旧名は、どの出所から来ても採用しない（後述）。
# docker の識別子として使うため、小文字英数と `-` `_` に正規化する。正規化しても
# 空になる（記号だけ等）場合は、名前を人に決めてもらう。
normalize_app_name() {
  printf '%s' "$1" | tr '[:upper:]' '[:lower:]' | sed -e 's/[^a-z0-9_-]/-/g' -e 's/^[^a-z0-9]*//'
}

APP_NAME="$(env_file_value APP_NAME)"
APP_NAME_SOURCE=".env の APP_NAME"
if [ -z "$APP_NAME" ]; then
  APP_NAME="$(normalize_app_name "$(basename "$(dirname "$BASE_DIR")")")"
  APP_NAME_SOURCE="配置ディレクトリ"
fi
if [ -z "$APP_NAME" ]; then
  APP_NAME="$BUILD_APP_NAME"
  APP_NAME_SOURCE="ビルド時の既定値"
fi

# 旧アプリ名は「引退した名前」であって、選べる名前ではない。配置ディレクトリが
# 旧名のままだったり、旧名の頃に自動生成された .env の APP_NAME が残っていたりすると、
# 名前の出所としては正しく解決できてしまい、いつまでも旧名でコンテナが作られ続ける。
# 解決結果が旧名に当たったらビルド時の名前へ倒す。ここで倒しておくことで、この後の
# migrate_legacy_env_names（.env の焼き付き）と take_down_legacy_projects（旧名で
# 動いているコンテナ）も本来の移行経路として働く。
#
# 倒したときは移行元を LEGACY_NAME_MIGRATED_FROM に控える。この配置は「旧名で動いて
# いるコンテナが自分のものである」場所なので、それを畳めないまま up へ進むと、旧名の
# MariaDB と新しい名前の MariaDB が同じ HOST_DATA_ROOT/db_data を同時に掴む
# （container_name もネットワーク名も新旧で異なるため、衝突で止まってくれない）。
# take_down_legacy_projects はこの印を見て、畳めないときに続行せず落とす。
LEGACY_NAME_MIGRATED_FROM=""
for legacy_name in $LEGACY_APP_NAMES; do
  [ "$APP_NAME" = "$legacy_name" ] || continue
  warn "${APP_NAME_SOURCE}から旧アプリ名 '$legacy_name' が解決されました。引退した名前のため '$BUILD_APP_NAME' を使います。"
  warn "この警告を消すには、配置ディレクトリを '$BUILD_APP_NAME' へ改名し（.env の HOST_DATA_ROOT も新しいパスへ直す）、.env の APP_NAME 指定を外してください。"
  APP_NAME="$BUILD_APP_NAME"
  APP_NAME_SOURCE="ビルド時の既定値（旧アプリ名 '$legacy_name' からの移行）"
  LEGACY_NAME_MIGRATED_FROM="$legacy_name"
  break
done

# ===== 環境判定（配置ディレクトリ名で stg / prod を切り替える） =====
# ENV_KIND（stg / prod）が分類の正。以降の分岐は ENV_NAME の字面ではなく ENV_KIND で行う
# （staging・*-stg 等のエイリアスに prod 既定値を適用してしまわないため）。
case "$ENV_NAME" in
  stg | staging | *-stg | *-staging)
    ENV_KIND=stg
    PROJECT="${APP_NAME}-stg"
    DEFAULT_WEB_HOST_PORT=8081
    ;;
  prod | production | *-prod | *-production)
    ENV_KIND=prod
    PROJECT="${APP_NAME}"
    DEFAULT_WEB_HOST_PORT=8080
    ;;
  *)
    echo "[deploy][error] このスクリプトは <アプリ名>/<stg|prod>/ 配下に配置して実行してください。" >&2
    echo "  現在の配置: $BASE_DIR（環境ディレクトリ名 '$ENV_NAME' が stg / prod 系ではありません）" >&2
    exit 1
    ;;
esac

APP_IMAGE="${APP_NAME}:$ENV_NAME"
DB_IMAGE="${APP_NAME}-db:$ENV_NAME"
IMAGE_TAR="$BASE_DIR/image.tar"
IMAGE_DB_TAR="$BASE_DIR/image-db.tar"
COMPOSE_FILE="$BASE_DIR/docker-compose.yml"
MANIFEST_ENV="$BASE_DIR/manifest.env"
MANIFEST_SHA="$BASE_DIR/manifest.sha256"

# ===== manifest（build.sh の出力メタデータ。無ければ従来どおり動く） =====
# ロード時タグ・イメージ ID・commit を manifest から取り、配置物とビルド成果の齟齬を検出する。
# 既定値は APP_NAME ではなく BUILD_APP_NAME から作る。ここで欲しいのは「デプロイの
# 名前」ではなく「tar の中身がどう tag されているか」で、配置ディレクトリを変えても
# tar の中身は変わらないため。
LOADED_APP_REF="${BUILD_APP_NAME}:latest"
LOADED_DB_REF="${BUILD_APP_NAME}-db:latest"
MANIFEST_APP_IMAGE_ID=""
MANIFEST_DB_IMAGE_ID=""
MANIFEST_COMMIT=""
if [ -f "$MANIFEST_ENV" ]; then
  # shellcheck disable=SC1090
  . "$MANIFEST_ENV"
  LOADED_APP_REF="${app_ref:-$LOADED_APP_REF}"
  LOADED_DB_REF="${db_ref:-$LOADED_DB_REF}"
  MANIFEST_APP_IMAGE_ID="${app_image_id:-}"
  MANIFEST_DB_IMAGE_ID="${db_image_id:-}"
  MANIFEST_COMMIT="${commit:-}"
fi

# tar が manifest.sha256 の checksum と一致するか検証する（転送破損の早期検出）。
# manifest が無い・sha256sum が無い・該当エントリが無い場合は従来どおりスキップする。
verify_tar_checksum() { # 引数: tar のファイル名（BASE_DIR 直下）
  local name="$1"
  [ -f "$MANIFEST_SHA" ] || return 0
  command -v sha256sum >/dev/null 2>&1 || return 0
  grep -qE "  ${name}\$" "$MANIFEST_SHA" || return 0
  ( cd "$BASE_DIR" && grep -E "  ${name}\$" "$MANIFEST_SHA" | sha256sum -c - >/dev/null 2>&1 ) \
    || return 1
  return 0
}

# ロード済みイメージが manifest のイメージ ID と一致していれば docker load を省略できる。
image_matches_manifest() { # 引数: <イメージ参照> <期待イメージID>
  local ref="$1" expected="$2" actual
  [ -n "$expected" ] || return 1
  actual="$(docker image inspect -f '{{.Id}}' "$ref" 2>/dev/null || true)"
  [ -n "$actual" ] && [ "$actual" = "$expected" ]
}

# マウントルート。既定は環境ディレクトリ配下の mnt/（.env の HOST_DATA_ROOT で上書き可）。
HOST_DATA_ROOT="$(env_file_value HOST_DATA_ROOT)"
HOST_DATA_ROOT="${HOST_DATA_ROOT:-$BASE_DIR/mnt}"
DATA_PATH="$HOST_DATA_ROOT/data"
DB_PATH="$HOST_DATA_ROOT/db_data"

WEB_HOST_PORT="$(env_file_value WEB_HOST_PORT)"
WEB_HOST_PORT="${WEB_HOST_PORT:-$DEFAULT_WEB_HOST_PORT}"
HEALTH_URL="http://127.0.0.1:${WEB_HOST_PORT}/healthz"

# compose interpolation はシェル環境変数 > --env-file の優先順位のため、ここで
# export した値が優先される。stg / prod が同一ホストでイメージを取り合わないよう
# 環境別タグに統一する。
export HOST_DATA_ROOT
export WEB_IMAGE="$APP_IMAGE"
export DB_IMAGE

COMPOSE="docker compose -p $PROJECT -f $COMPOSE_FILE --env-file $ENV_FILE"

MODE="${1:-}"

case "$MODE" in
  app|migrate|reset) ;;
  *)
    err "Mode required. Usage: $0 <app|migrate|reset>"
    exit 1
    ;;
esac

# ===== エラー時診断: 失敗したモジュールのログを出して終了する =====
ALL_SERVICES=(init-paths db web nginx)

dump_module_logs() { # 引数: サービス名...
  echo "" >&2
  echo "----- diagnostics ($TAG) -----" >&2
  $COMPOSE ps -a >&2 || true
  local svc
  for svc in "$@"; do
    echo "" >&2
    echo "$TAG ---- module logs: $svc (last 100 lines) ----" >&2
    $COMPOSE logs --tail 100 --timestamps "$svc" >&2 || true
  done
  echo "------------------------------" >&2
}

fail() { # 引数: メッセージ [ログを出すサービス名...]
  local msg="$1"
  shift || true
  err "$msg"
  if [ $# -gt 0 ]; then
    dump_module_logs "$@"
  fi
  err "Deploy failed (mode: $MODE, env: $ENV_NAME)"
  exit 1
}

on_unexpected_error() {
  local line="$1"
  err "Unexpected error at line $line (mode: $MODE)"
  dump_module_logs "${ALL_SERVICES[@]}"
  err "Deploy failed (mode: $MODE, env: $ENV_NAME)"
  exit 1
}
trap 'on_unexpected_error $LINENO' ERR

log "${APP_NAME} deploy start (env: $ENV_NAME, mode: $MODE, base: $BASE_DIR)"
# どの名前でコンテナ・イメージ・ネットワークが作られるかは、この 1 行で分かるようにする。
log "app name: $APP_NAME（$APP_NAME_SOURCE より）/ compose project: $PROJECT"

# ===== Preflight: docker daemon must be reachable =====
if ! docker info >/dev/null 2>&1; then
  err "Cannot reach the Docker daemon (permission denied or daemon down)."
  echo "  Run this script with sudo, or add your user to the 'docker' group and re-login." >&2
  exit 1
fi

log "Mount root: $HOST_DATA_ROOT"

load_image() {
  local tar="$1"
  log "Loading image: $tar ($(du -h "$tar" 2>/dev/null | cut -f1))"
  docker load -i "$tar"
}

retag_for_env() { # 引数: <ロード時タグ> <環境別タグ>
  local loaded="$1" target="$2"
  docker tag "$loaded" "$target" || fail "Failed to tag $loaded as $target"
  log "Tagged $loaded -> $target"
}

# ===== Load app image =====
if [ -n "$MANIFEST_COMMIT" ]; then
  log "Manifest: commit=$MANIFEST_COMMIT version=${version:-unknown} build=${build_date:-unknown}"
fi
if [ -f "$IMAGE_TAR" ]; then
  verify_tar_checksum "$(basename "$IMAGE_TAR")" \
    || fail "image.tar が manifest.sha256 と一致しません（転送破損の可能性。dist/ を配置し直してください）"
  if image_matches_manifest "$LOADED_APP_REF" "$MANIFEST_APP_IMAGE_ID"; then
    log "App image already loaded ($LOADED_APP_REF matches manifest); skipping docker load"
  else
    load_image "$IMAGE_TAR"
  fi
  retag_for_env "$LOADED_APP_REF" "$APP_IMAGE"
elif docker image inspect "$APP_IMAGE" >/dev/null 2>&1; then
  warn "Image tar not found: $IMAGE_TAR — reusing already-loaded $APP_IMAGE"
else
  err "Image tar not found: $IMAGE_TAR"
  echo "  ビルドマシンで './scripts/build.sh' を実行し、dist/ の中身を配置してください。" >&2
  exit 1
fi

# ===== Sync deploy assets from the loaded image =====
# 配置先の compose / nginx 設定が古いまま残る事故を防ぐため、イメージに焼き込まれた
# コピーをロード直後に取り出し、常にイメージと同じ版を使う。環境ごとの違いは
# すべて .env 側で表現する。
sync_assets_from_image() {
  local cid
  if ! cid=$(docker create "$APP_IMAGE" 2>/dev/null); then
    warn "Could not inspect $APP_IMAGE; skipping asset sync"
    return 0
  fi

  if docker cp "$cid:/app/docker-compose.yml" "$COMPOSE_FILE.new" >/dev/null 2>&1; then
    mv -f "$COMPOSE_FILE.new" "$COMPOSE_FILE"
    log "compose file synced from image -> $COMPOSE_FILE"
  else
    rm -f "$COMPOSE_FILE.new"
    warn "$APP_IMAGE has no /app/docker-compose.yml; keeping existing file if any"
  fi

  local nginx_conf_dst="$BASE_DIR/docker/nginx/default.conf"
  mkdir -p "$(dirname "$nginx_conf_dst")"
  if docker cp "$cid:/app/docker/nginx/default.conf" "$nginx_conf_dst.new" >/dev/null 2>&1; then
    mv -f "$nginx_conf_dst.new" "$nginx_conf_dst"
    log "nginx config synced from image -> $nginx_conf_dst"
  else
    rm -f "$nginx_conf_dst.new"
    warn "$APP_IMAGE has no nginx config; keeping existing file if any"
  fi

  docker rm -f "$cid" >/dev/null 2>&1 || true
}
sync_assets_from_image

if [ ! -f "$COMPOSE_FILE" ]; then
  fail "No docker-compose.yml found at $COMPOSE_FILE (image sync also failed)"
fi

# ===== Ensure .env exists (zero-config deploy) =====
# 値はすべて docker-compose.yml 側の ${VAR:-default} が供給するので、生成する
# .env は上書き用のコメント付きテンプレートで足りる。既存の .env には触れない。
if [ ! -f "$ENV_FILE" ]; then
  warn "$ENV_FILE not found; generating a default template."
  if [ "$ENV_KIND" = "stg" ]; then
    DEFAULT_DB_CONTAINER="${APP_NAME}-mariadb-stg"
    DEFAULT_NETWORK="${APP_NAME}-stg"
  else
    DEFAULT_DB_CONTAINER="${APP_NAME}-mariadb"
    DEFAULT_NETWORK="${APP_NAME}-prod"
  fi
  cat > "$ENV_FILE" <<ENVEOF
# 自動生成された .env（deploy スクリプトが作成。環境: $ENV_NAME）。
# 既定の資格情報は開発向け。外部公開する場合は必ず上書きして再デプロイする。
# すべての項目は .env.example を参照。

# --- 環境固有の実値（この環境ディレクトリに閉じた値に固定する）---
HOST_DATA_ROOT=$BASE_DIR/mnt
WEB_HOST_PORT=$WEB_HOST_PORT
DB_CONTAINER_NAME=$DEFAULT_DB_CONTAINER
DOCKER_NETWORK_NAME=$DEFAULT_NETWORK

# --- 上書き推奨（未設定なら開発向け既定値で動作する）---
# MARIADB_ROOT_PASSWORD=strong-mariadb-root-password-here
# MARIADB_USER=web_user
# MARIADB_PASSWORD=strong-mariadb-password-here
# MARIADB_DATABASE=appdb
# JWT_SECRET_KEY=strong-random-secret-here
# SECRET_KEY=strong-random-secret-here
# APP_BASE_URL=https://app.example.com
# ADMIN_INITIAL_PASSWORD=change-me-strong

# アプリ名は配置ディレクトリ（この .env の 2 つ上の階層）の名前から決まる。
# ディレクトリ名を使えないときだけ、ここで明示する。
# APP_NAME=$APP_NAME
ENVEOF
fi

# ===== 旧アプリ名で焼き付いた .env の値を移す（名前変更の一度きりの移行） =====
# 生成した .env に入る DB_CONTAINER_NAME / DOCKER_NETWORK_NAME は、この環境
# ディレクトリに閉じた「スクリプトが決めた名前」であって運用者の設定値ではない。
# 旧名のまま残すと、元テンプレート（同じ名前を使う別プロジェクト）と
# container_name / ネットワーク名を奪い合う。旧既定値と一致するときだけ書き換え、
# 運用者が自分で決めた値には触れない。
migrate_legacy_env_names() {
  [ -f "$ENV_FILE" ] || return 0
  local legacy key current expected
  for legacy in $LEGACY_APP_NAMES; do
    # 念のための番人。アプリ名の解決時に旧名は弾いてあるので、通常ここは成立しない。
    [ "$legacy" = "$APP_NAME" ] && continue
    for key in DB_CONTAINER_NAME DOCKER_NETWORK_NAME; do
      current="$(env_file_value "$key")"
      [ -n "$current" ] || continue
      case "$key" in
        DB_CONTAINER_NAME)
          [ "$ENV_KIND" = "stg" ] && expected="${legacy}-mariadb-stg" || expected="${legacy}-mariadb"
          ;;
        *)
          [ "$ENV_KIND" = "stg" ] && expected="${legacy}-stg" || expected="${legacy}-prod"
          ;;
      esac
      [ "$current" = "$expected" ] || continue
      local replacement="${expected/#$legacy/$APP_NAME}"
      log "$ENV_FILE: $key を旧アプリ名から移行します（$current -> $replacement）"
      sed -i.bak -E "s|^${key}=.*|${key}=${replacement}|" "$ENV_FILE" && rm -f "$ENV_FILE.bak"
    done
  done
}
migrate_legacy_env_names

# compose の default ネットワーク名（docker-compose.yml の
# `${DOCKER_NETWORK_NAME:-rewardpointsweb}` と同じ解決をここでも行う）。
# .env を生成・移行した後で読むこと。初回デプロイでは生成された .env に環境別の
# 名前（rewardpointsweb-prod 等）が入るため、先に読むと素の既定値を見てしまう。
DOCKER_NETWORK_NAME="$(env_file_value DOCKER_NETWORK_NAME)"
DOCKER_NETWORK_NAME="${DOCKER_NETWORK_NAME:-$APP_NAME}"

# ===== Ensure DB image is available under the env-specific tag =====
ensure_db_image() {
  if docker image inspect "$DB_IMAGE" >/dev/null 2>&1; then
    return 0
  fi
  if [ -f "$IMAGE_DB_TAR" ]; then
    verify_tar_checksum "$(basename "$IMAGE_DB_TAR")" \
      || fail "image-db.tar が manifest.sha256 と一致しません（転送破損の可能性。dist/ を配置し直してください）"
    load_image "$IMAGE_DB_TAR"
    retag_for_env "$LOADED_DB_REF" "$DB_IMAGE"
    return 0
  fi
  if docker image inspect "$LOADED_DB_REF" >/dev/null 2>&1; then
    retag_for_env "$LOADED_DB_REF" "$DB_IMAGE"
    return 0
  fi
  fail "DB image not found: $DB_IMAGE（'./scripts/build.sh' で dist/image-db.tar を作成し配置してください）"
}

# ===== Docker ネットワークの重複解消 =====
# docker daemon はネットワーク「名」の一意性を保証しない（一意なのは ID だけ）。
# down が途中で失敗して古いネットワークが残ったまま up したり、compose の作成が
# 競合したりすると同じ名前のネットワークが 2 つでき、以降は名前で参照できなくなる。
# そうなるとコンテナの起動が
# `network <name> is ambiguous (N matches found on name)` で必ず失敗する。
# ネットワーク自体は永続データを持たないので、重複を見つけたら全部消して
# compose に 1 つだけ作り直させる。
network_ids_by_name() { # 引数: ネットワーク名（完全一致）
  docker network ls --format '{{.ID}} {{.Name}}' \
    | awk -v name="$1" '$2 == name { print $1 }'
}

count_nonempty_lines() { # 標準入力の行数（0 件でも 0 を出して成功で返す）
  grep -c . || true
}

network_endpoint_ids() { # 引数: ネットワーク ID → 接続中コンテナの ID
  docker network inspect -f '{{range $cid, $c := .Containers}}{{$cid}} {{end}}' "$1" 2>/dev/null \
    || true
}

# このプロジェクト以外のコンテナが繋がっていれば、その名前を出力する。
# 既に存在しないコンテナ（残骸のエンドポイント）は無視する。
foreign_endpoints() { # 引数: ネットワーク ID
  local cid info name
  for cid in $(network_endpoint_ids "$1"); do
    info="$(
      docker inspect -f '{{index .Config.Labels "com.docker.compose.project"}}|{{.Name}}' "$cid" 2>/dev/null
    )" || continue
    [ "${info%%|*}" = "$PROJECT" ] && continue
    name="${info#*|}"
    printf '%s\n' "${name#/}"
  done
}

remove_network() { # 引数: ネットワーク ID
  local id="$1" endpoint
  # 接続中のコンテナが残っていると削除できないため、先に切り離す。ここへ来る時点で
  # 繋がっているのはこのプロジェクトのものだけ（resolve_duplicate_networks が検査済み）。
  for endpoint in $(network_endpoint_ids "$id"); do
    docker network disconnect -f "$id" "$endpoint" >/dev/null 2>&1 || true
  done
  docker network rm "$id" >/dev/null 2>&1 || true
}

# 同名ネットワークが 2 つ以上あれば削除する。解消できなければ非 0 を返す。
resolve_duplicate_networks() {
  local ids count foreign id
  ids="$(network_ids_by_name "$DOCKER_NETWORK_NAME")"
  count="$(printf '%s' "$ids" | count_nonempty_lines)"
  [ "$count" -gt 1 ] || return 0

  # このプロジェクト以外のコンテナが繋がっているときは何もしない。切り離すと
  # そのコンテナは動いたまま通信できなくなり、続く up でも復旧しないため
  # （OPERATIONS.md のとおり、保守用のコンテナをこのネットワークへ繋ぐ運用がある）。
  foreign="$(for id in $ids; do foreign_endpoints "$id"; done | sort -u | tr '\n' ' ')"
  if [ -n "${foreign// /}" ]; then
    err "Docker network '$DOCKER_NETWORK_NAME' is duplicated, but containers outside this project are attached: ${foreign% }"
    err "先にそれらのコンテナを停止するか別のネットワークへ移してから、デプロイし直してください。"
    return 1
  fi

  warn "Docker network '$DOCKER_NETWORK_NAME' is duplicated ($count networks share the name); removing them so compose can recreate a single one"
  for id in $ids; do
    remove_network "$id"
  done
  count="$(network_ids_by_name "$DOCKER_NETWORK_NAME" | count_nonempty_lines)"
  [ "$count" -le 1 ] && return 0
  err "'docker network ls' で ID を確認し、'docker network rm <ID>' で 1 つだけ残して削除してください。"
  return 1
}

# ===== Stop running containers =====
# down が途中で失敗するとネットワークが残り、次の up が同名のものを作って
# ambiguous になる。コンテナを強制削除してでも down を最後まで通す。
compose_down() {
  $COMPOSE down --remove-orphans && return 0
  warn "docker compose down failed; force-removing project containers and retrying"
  local cid
  for cid in $(docker ps -aq --filter "label=com.docker.compose.project=$PROJECT" 2>/dev/null || true); do
    docker rm -f "$cid" >/dev/null 2>&1 || true
  done
  $COMPOSE down --remove-orphans || warn "docker compose down still failed; continuing"
}

# ===== 旧アプリ名の compose プロジェクトを畳む（名前変更の一度きりの移行） =====
# compose プロジェクト名も APP_NAME から導くため、名前を変えた直後の down は
# 新プロジェクトを見に行き、旧名で動いているコンテナを見つけられない。放置すると
# 同じ container_name とホストポートを握ったまま残り、続く up が必ず失敗する。
#
# ただし「旧アプリ名の compose プロジェクト」は、まさに共存させたい**本物の別アプリ**
# かもしれない（同じ名前を使っていたのがこの改名の理由）。プロジェクト名ラベルでの
# 絞り込みは docker デーモン全体を見るため、それだけを根拠に down すると無関係の
# アプリを停止・削除してしまう。compose が付ける working_dir ラベルがこの環境
# ディレクトリと一致するコンテナ（＝過去にこのディレクトリから起動したもの）だけを
# 自分のものとみなし、1 つでも他所のものが混ざっていたら何もしない。
legacy_container_names_outside_this_deployment() { # 引数: コンテナ ID の並び
  local cid working_dir name
  for cid in $1; do
    working_dir="$(
      docker inspect -f '{{index .Config.Labels "com.docker.compose.project.working_dir"}}' "$cid" 2>/dev/null
    )" || working_dir=""
    # ラベルが読めないもの（compose v1 期の残骸等）は「自分のものと確認できない」
    # 側に倒す。触らずに人へ委ねるほうが、消して壊すより安い。
    [ "$working_dir" = "$BASE_DIR" ] && continue
    name="$(docker inspect -f '{{.Name}}' "$cid" 2>/dev/null)" || name="$cid"
    printf '%s\n' "${name#/}"
  done
}

take_down_legacy_projects() {
  local legacy project cids foreign
  for legacy in $LEGACY_APP_NAMES; do
    [ "$ENV_KIND" = "stg" ] && project="${legacy}-stg" || project="${legacy}"
    # 念のための番人。アプリ名の解決時に旧名は弾いてあるので、通常ここは成立しない。
    # （成立するなら旧名が今回のプロジェクト自身なので、直後の compose_down が畳む。）
    [ "$project" = "$PROJECT" ] && continue
    cids="$(docker ps -aq --filter "label=com.docker.compose.project=$project" 2>/dev/null || true)"
    [ -n "$cids" ] || continue

    foreign="$(legacy_container_names_outside_this_deployment "$cids" | sort -u | tr '\n' ' ')"
    if [ -n "${foreign// /}" ]; then
      # この配置自身が旧名から移行してきた場合、旧名のコンテナは「同じ HOST_DATA_ROOT
      # を使っていた自分の前身」である可能性が高い。畳めないまま up へ進むと、新旧 2 つの
      # MariaDB が同じ db_data を同時に開く（container_name もネットワーク名も新旧で
      # 異なるので衝突は起きず、compose は db を healthy まで持っていってしまう。止まるのは
      # 後段の nginx がホストポートを取れないときで、そのときには既に手遅れ）。
      # データを壊すより止める。畳めない理由（ラベルが読めない = compose v1 期の残骸等）は
      # 人が見て判断する。
      if [ "$legacy" = "$LEGACY_NAME_MIGRATED_FROM" ]; then
        err "旧アプリ名の compose プロジェクト '$project' を畳めません。この配置（$BASE_DIR）のものと確認できないコンテナが含まれます: ${foreign% }"
        err "この配置は '$legacy' から '$APP_NAME' へ移行した直後のため、そのまま起動すると新旧 2 つの MariaDB が同じ $HOST_DATA_ROOT/db_data を同時に開き、DB を壊します。"
        fail "上記コンテナを確認し、この配置の前身なら 'docker rm -f' で消してから再実行してください（別アプリなら配置ディレクトリ名を変えて名前を分けてください）。"
      fi
      warn "旧アプリ名の compose プロジェクト '$project' が動いていますが、この配置（$BASE_DIR）以外のコンテナを含むため触りません: ${foreign% }"
      warn "同じ名前を使う別のアプリだと思われます。'$PROJECT' の起動が container_name やポートの衝突で失敗する場合は、どちらの名前を変えるか決めてください。"
      continue
    fi

    warn "旧アプリ名の compose プロジェクト '$project' が残っています。新しい名前 '$PROJECT' へ移行するため畳みます。"
    docker compose -p "$project" -f "$COMPOSE_FILE" --env-file "$ENV_FILE" down --remove-orphans \
      || warn "'$project' の down に失敗しました。続行します（up が失敗する場合は手動で削除してください）。"
  done
}
take_down_legacy_projects

log "docker compose down"
compose_down

# ===== Reset mode: clear data =====
if [ "$MODE" = "reset" ]; then
  echo -e "\033[33m[reset] WARNING: This will delete all $ENV_NAME DB & app data.\033[0m"
  if [ -f "$IMAGE_DB_TAR" ]; then
    verify_tar_checksum "$(basename "$IMAGE_DB_TAR")" \
      || fail "image-db.tar が manifest.sha256 と一致しません（転送破損の可能性。dist/ を配置し直してください）"
    load_image "$IMAGE_DB_TAR"
    retag_for_env "$LOADED_DB_REF" "$DB_IMAGE"
  else
    warn "[reset] DB image tar not found: $IMAGE_DB_TAR"
  fi
  echo "[reset] Deleting $DB_PATH and $DATA_PATH"
  rm -rf "$DB_PATH" "$DATA_PATH"
fi

ensure_db_image

# ===== Ensure the host mount root exists =====
# バインドマウント元が無いとコンテナが一切起動しない（ログも残らない）ため、
# マウントルートだけはここで確実に作る。サブディレクトリは init-paths が作る。
log "Ensuring host mount root exists: $HOST_DATA_ROOT"
mkdir -p "$HOST_DATA_ROOT" || fail "Could not create host mount root: $HOST_DATA_ROOT"

# ===== Start containers =====
# 起動前に同名ネットワークの重複を解消しておく（残っていると up が必ず失敗する）。
resolve_duplicate_networks \
  || fail "Could not resolve the duplicated Docker network '$DOCKER_NETWORK_NAME'（復旧手順は docs/OPERATIONS.md「デプロイが network ... is ambiguous で失敗したとき」）"

UP_OUTPUT="$(mktemp)"

start_containers() { # 起動を 1 回試す。出力は画面と $UP_OUTPUT の両方へ
  $COMPOSE up -d --remove-orphans 2>&1 | tee "$UP_OUTPUT"
}

fail_up() {
  rm -f "$UP_OUTPUT"
  fail "docker compose up failed" "${ALL_SERVICES[@]}"
}

log "docker compose up -d"
if ! start_containers; then
  # compose 自身が同名ネットワークを二重に作った場合は、ここで初めて分かる。
  # 掃除して 1 度だけやり直す。
  if grep -q "is ambiguous" "$UP_OUTPUT" && resolve_duplicate_networks; then
    warn "Retrying 'docker compose up' after cleaning up the duplicated network"
    start_containers || fail_up
  else
    fail_up
  fi
fi
rm -f "$UP_OUTPUT"

# ===== Schema sync =====
run_migrations_with_retry() {
  local attempt
  for attempt in 1 2 3; do
    if $COMPOSE exec -T web python scripts/run_db_migrations.py; then
      return 0
    fi
    warn "DB migration failed (attempt $attempt/3); retrying in 5s"
    sleep 5
  done
  fail "DB migration failed after 3 attempts" web db
}

case "$MODE" in
  migrate|reset)
    # migrate: 既存データを保持したまま新しい migration だけを適用する。
    # reset: 空 DB にスキーマ + マスタデータを構築する（entrypoint も冪等に流すが
    # ここでも確実に head まで揃える）。
    log "Applying DB migrations"
    run_migrations_with_retry
    ;;
esac

# ===== Wait for health check =====
log "Waiting for service health: $HEALTH_URL"
for i in $(seq 1 60); do
  if curl -fs "$HEALTH_URL" >/dev/null 2>&1; then
    log "Service healthy"
    break
  fi
  log "...waiting ($i/60)"
  sleep 2
done

if ! curl -fs "$HEALTH_URL" >/dev/null 2>&1; then
  err "Health check failed: $HEALTH_URL"
  dump_module_logs web nginx
  err "Deploy failed (mode: $MODE, env: $ENV_NAME)"
  exit 1
fi

# ===== Cleanup old images =====
log "Cleaning old unused Docker images"
docker image prune -f > /dev/null 2>&1 || true

# ===== Show deployed version =====
log "Deployed version:"
$COMPOSE exec -T web cat /app/shared/kernel/version.json 2>/dev/null || warn "Could not read version.json"

echo -e "\033[32m${TAG} Deploy complete (mode: $MODE)\033[0m"
