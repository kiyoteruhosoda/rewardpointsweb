# ARCHITECTURE — 設計ガイド

本テンプレートのレイヤー構成・命名規則・DDD 実装パターンを解説する。
操作手順は `OPERATIONS.md`、設定キー一覧は管理画面（Config）を参照。

## レイヤー構成（DDD 4層）

```
Presentation → Application → Domain ← Infrastructure
```

- **Domain** — ビジネスロジック。フレームワーク・DB に依存しない純粋な Python。
  エンティティ（`dataclass`）、値オブジェクト（`frozen dataclass`）、
  リポジトリインターフェース（`ABC`）、ドメイン例外。
- **Application** — ユースケース・トランザクション境界。DTO への変換もここで行う。
- **Infrastructure** — Domain のリポジトリインターフェースを SQLAlchemy 等で実装する。
- **Presentation** — FastAPI Router と Pydantic Schema。HTTP の関心事のみ。

依存方向は Presentation → Application → Domain。
Infrastructure は Domain のインターフェースを実装する（依存性逆転）。

この向きは `tests/unit/test_layer_dependencies.py` が AST で検証する。禁止するのは
**逆流**で、次の向きは import した時点でテストが落ちる。

| 層 | 依存できない先 |
|---|---|
| Domain | Application / Infrastructure / Presentation |
| Application | Infrastructure / Presentation |
| Infrastructure | Application / Presentation |

Domain がフレームワーク・DB（`fastapi` / `sqlalchemy` / `pydantic` 等）を import
することも同様に落ちる。

`Presentation → Infrastructure` は**禁止しない**。最も外側の層が具体実装を組み立てて
`Depends()` に渡すのは正しい向きで、DI の配線はどこかで行う必要がある（ADR-0006）。

## bounded_contexts と shared の使い分け

- 機能は `bounded_contexts/<context>/` として追加する。1コンテキスト = 1業務領域。
  `bounded_contexts/example/`（Item CRUD）が最小構成の見本。
- 複数コンテキストから使う横断的な要素だけを `shared/` に置く:
  - `shared/domain/auth/` — 認可マスタデータ（`master_data.py` が唯一の出所）
  - `shared/infrastructure/models/` — 共有 SQLAlchemy モデル（User / Role / Permission /
    SystemSetting / Log / PasswordResetToken）
  - `shared/kernel/` — settings / logging / database / restart / scheduling / timestamps
    （技術基盤。ドメイン知識を持たない）
- `presentation/fastapi/` はコンテキスト横断の API（認証・管理系）と
  アプリケーションファクトリ（`app.py`）を持つ。

## 認証・認可の設計

- 認証は JWT（access / refresh の2トークン）。発行・検証は
  `presentation/fastapi/services/token_service.py`。
- 認可は **scope（権限コード値）** ベース。ロール名で分岐しない。
  - 有効 scope = ユーザーの全ロールが持つ権限の和集合。
  - エンドポイントでは `Depends(require_permission("user:manage"))` のように宣言する。
  - 検証済みの主体は `AuthenticatedPrincipal`（`shared/application/`）として渡る。
- ロール・権限コード・初期管理者は `shared/domain/auth/master_data.py` で一元管理し、
  マイグレーションのシードと `scripts/seed_master_data.py` が参照する。

- 第二の要素（二要素認証・パスキー）は `bounded_contexts/account_security/` が持つ
  （ADR-0003）。パスワード認証は上記のまま、ログイン時に TOTP を検証する／パスキー
  だけでトークンを発行する、という形で足している。詳細はコンテキストの README。

サービスアカウント認証・外部 IdP 連携は初期スコープに含めない（ADR-0002）。

### scope で表せない「対象ごとの認可」

scope は「その操作を行える立場か」を表す。「*その* データを触れるか」は表せない
（誰のデータかという関係が scope に現れない）。関係で決まる認可が必要な場合は、
**scope をエンドポイントに宣言したうえで、対象ごとの判定を Domain のポリシーに置く**
二段構えにする。

`reward_points` がこの形（ADR-0009）。`family:*` / `point:*` の scope で立場を見て、
`family_access_policy` が家族の中での立場（owner / parent / child）から
「その台帳を見られるか・変えられるか」を決める。`point:manage` を持っていても、
所属していない家族の台帳は触れない。判定は Application 層の
`FamilyAccessResolver` を通す一点に集約し、ユースケースが個別に条件を書かない
ようにする。

家族はデータ分離の明示的な境界でもある。所属していない家族・見えない台帳には
**404** を返す（403 だと「その ID は存在する」ことが分かってしまう）。

## 自己再起動の設計

管理画面から保存した設定のうち、起動時にしか読まれないもの（ログ・CORS）は
保存だけでは反映されない。`shared/kernel/restart/` がその橋渡しをする。

- 設定定義の `restart_scopes` が「反映にどのサービスの再起動が要るか」を宣言する。
- 管理 API は要求を DB（`system_settings` の `app.restart_request`）へ書く。
- 各プロセスは起動時に `RestartWatcher` を立て、自分宛の要求の token が変わったら
  自分自身を終了させる。復帰はコンテナの restart policy に任せる。

要求を DB 経由にするのは、管理 API を処理したプロセスと再起動すべきプロセスが
別だから（Gunicorn は複数ワーカー）。判定を時刻ではなく token の変化で行うのは、
時計のずれで再起動ループに陥らないようにするため（ADR-0004）。

## 定期実行の設計

誰の要求もきっかけにならない処理（毎日のボーナスの付与）は
`shared/kernel/scheduling/` の `PeriodicRunner` が回す。決まった間隔で 1 周し、
1 周が例外で終わってもスレッドは生き続ける（止まると以後の処理が誰にも気付かれない
まま行われなくなる）。起動直後にも 1 周走るので、止まっていたあいだの取りこぼしは
再起動と同時に片付く。

**1 回だけの実行は保証しない。** Gunicorn のワーカーごとにスレッドが立つため、
渡す処理は同時に走っても壊れないもの（冪等なもの）に限る。毎日のボーナスは冪等キーに
日付を持たせ、二重付与を DB の一意制約で止めている（ADR-0024）。排他ロックや
リーダー選出を持たないのは、ロックの取りこぼしと解放漏れという別の問題を
抱え込まないため。

## 設定管理の設計

`shared/kernel/settings/settings.py` の `ApplicationSettings` が
「環境変数 > DB（system_settings テーブル）> デフォルト値」の優先順位で値を解決する。

- DB 層は TTL キャッシュ付き。管理画面からの保存時は
  `SystemSettingService` が `invalidate()` を呼び即時反映する。
- DB 未接続（マイグレーション前等）では環境変数とデフォルト値のみで動く。読めない
  状態に入った／戻ったときだけログへ 1 行残す（TTL ごとに出すと溢れるため）。
- `DATABASE_URI` などブートストラップに必要なキーは DB 上書きの対象外
  （解決に DB 接続が必要なキーを DB から読むと再帰するため）。

## ログの設計

- `presentation/fastapi/middleware/request_logging.py` がリクエストごとに
  `requestId` を採番し、`contextvars` 経由で全ログレコードへ伝播する。
- `shared/kernel/logging/db_log_handler.py` が JSON 構造化ログを `log` テーブルへ
  書き込む。stdout への JSON 出力と併用する。
- PII 禁止。ユーザー識別子はハッシュ（`user.id_hash`）のみ。

**失敗の記録は `presentation/fastapi/error_handling.py` に集約する**（ADR-0012）。
`HTTPException`・入力検証エラー・ドメイン例外は、送出された時点でルーターを抜けて
例外ハンドラが応答へ変えるため、ルーターに `logger` を足しても記録されない。

| 経路 | 記録するもの | ロガー |
|---|---|---|
| アクセスログ（ミドルウェア） | `http_request`（method / path / status / duration） | `app.request` |
| `HTTPException`・ドメイン例外 | `request_failed: <エラーコード>` | `presentation.fastapi.error_handling` |
| 入力検証エラー | `request_validation_failed: <項目名:理由>`（値は入れない） | 同上 |
| 想定外の例外 | `unhandled_exception`（+ traceback） | 同上 |
| 管理操作・ログイン失敗 | `<操作>: <識別子>`（下記） | 各ルーター |

- レベルはステータスコードから決める（`log_level_for_status()`）。5xx → ERROR、
  4xx → WARNING、401 と成功 → INFO。アクセスログと失敗の記録が同じ関数を使う。
  ログインの失敗だけは例外的に WARNING（このアプリに監査ログは無い）。
- 死活監視・メトリクスのパス（`/healthz` `/readyz` `/api/health` `/metrics`）は
  **成功したらアクセスログに残さない**（失敗は残す）。
- **識別子は `extra` ではなく本文（message）に入れる。** `log` テーブルへ入るのは
  列にある項目（`message` / `path` / `method` / `status_code` / `duration_ms` /
  `trace`）だけで、`extra` の残りは stdout の JSON にしか出ない。
- 管理操作（ユーザー・ロールの変更、システム設定の保存）はルーターから記録する。
  残すのは識別子と項目名だけで、表示名・メールアドレス・設定値は残さない。
- 新しいドメイン例外ハンドラを足すときは `log_failed_request()` を呼ぶ。
- ログ基盤自身の失敗は黙らせない。`DbLogHandler` は `handleError()`（stderr）で
  知らせ、設定の DB 読み取り不能は状態が変わったときだけ 1 行警告する。

リクエスト中のログ行は**控えに積むだけ**で、実際の INSERT はリクエストの処理が
完全に終わってから `DeferredLogWriteMiddleware` がまとめて行う。処理の途中で別
コネクションから書くと、リクエストのセッションが握った書き込みロックと衝突し、
SQLite では 5 秒待った末に行が失われる（ADR-0012）。

まとめ書きと例外の受け皿（`InternalErrorMiddleware`）は**素の ASGI ミドルウェア**
として書く。`BaseHTTPMiddleware` は下流を別のタスクで走らせるため、`get_db` の
commit を待てず、下流で設定された `contextvars`（`user_id_hash`）も戻ってこない。

## フロントエンド

`frontend/` は React + TypeScript + Vite の SPA スケルトン。
画面一覧・遷移図・各画面の仕様は `frontend/README.md`。

- `services/api.ts` — fetch ラッパー。JWT の保持・期限切れ時の refresh・401 処理。
- `store/` — 認証状態と、所属する家族（React Context）。家族の応答は残高も含めて
  ここに 1 つだけ置き、ナビゲーション・ダッシュボード・家族設定が共有する。
  内容を変えたら `reload()` を呼ぶ（ADR-0021）。
- `hooks/` — 画面をまたいで使う React フック。
- `pages/` — 画面単位。管理画面は scope で表示制御する。
- `i18n/` — 言語別 JSON（en / ja）。キーは英語。訳の抜けは
  `tests/unit/test_i18n_dictionaries.py` が検出する。
- `theme/` — テーマ（light / dark / system）。配色は `index.css` の CSS 変数で持ち、
  `<html data-theme>` を切り替えて解決する。
- 言語・テーマの既定値と選択肢は `GET /api/ui/settings`（公開）から受け取り、
  利用者の選択は `localStorage` に持つ（ADR-0005）。
- ビルド成果物（`frontend/dist`）は FastAPI の `routers/spa.py` が配信する。
  開発時は Vite dev server（`npm run dev`）から API へプロキシする。
- テストは対象と同じ階層に `*.test.ts(x)` として置く（Vitest + jsdom +
  Testing Library）。描画が例外を投げることの検証には
  `src/test-support/renderErrors.ts` を使う。

## 命名規則

- Pydantic スキーマ: `〇〇Request` / `〇〇Response`
- リポジトリインターフェース: `I〇〇Repository`（Domain）、実装は `Sql〇〇Repository` 等
- ユースケース: 動詞句のクラス名（`CreateItem`、`ListItems`）
- 権限コード: `<資源>:<操作>`（例 `user:manage`、`admin:system-settings`）
