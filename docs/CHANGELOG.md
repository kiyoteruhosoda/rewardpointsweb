# CHANGELOG — 完了した重要な変更の要約

新しいものを上に追記する。細かな進捗は書かない（Progress.md 完了時に要約を移す）。

## 2026-07 DB のホスト公開ポートを廃止

`db` はホストにポートを公開しなくなった（`ports` を外し `expose: 3306` のみ）。
到達できるのは同じ Docker ネットワークの中だけで、`web` は今までどおり
`db:3306` へ繋ぐ。ホストへ出すのは nginx だけになった。

以前は保守用に `127.0.0.1:3307`（stg は 3308）へ公開し、`.env` の `DB_BIND_ADDR` で
LAN へ開けられるようにしていた。ループバックに限っていても、ホストに入れる人・
同居する他のコンテナからは資格情報だけで DB に届いてしまう。保守は
`docker compose exec db` でコンテナ内から行えば足りるため、口そのものを閉じた。

- `.env` の `DB_BIND_ADDR` / `DB_HOST_PORT` は参照されなくなった（残っていても無害）。
  `deploy.sh` が生成する `.env` にも `DB_HOST_PORT` を書かない。
- stg / prod を同じホストで動かすときの DB ポート衝突（3307 / 3308 の振り分け）は
  なくなった。分離はコンテナ名とネットワーク名だけで足りる。
- 接続・ダンプ・リストアの手順は `OPERATIONS.md`「DB に直接つなぎたいとき」。

## 2026-07 人ごとのポイント（reward_points コンテキスト）と PWA 化

ネイティブアプリ（Flutter + SQLite の RewardPoints）を、この Web アプリへ移した。
端末内 DB からログイン付きの共有サーバーへ移ったことで、ネイティブ版には無かった
「誰のポイントか」「誰が触れるか」を決める必要が生まれた。

- **`bounded_contexts/reward_points/` を追加**（ADR-0007）。メンバー（ポイントを
  貯める人）・共有・履歴を扱う。認可は二段で、scope（`member:*` / `point:*`）が
  「その操作を行える立場か」を、`MemberAccessPolicy` が「そのメンバーを触れるか」を
  決める。`point:manage` を持つ管理者でも、共有されていないメンバーは触れない。
- **メンバー本人は閲覧のみ**。`members.linked_user_id` にログインアカウントを
  紐付けると、本人が自分の残高と履歴を見られる。変更は scope（`member` ロールに
  `point:manage` を与えない）と関係（本人は `view` 止まり）の両方で塞がれている。
- **共有はメールアドレスで指定する**。ユーザー一覧を返す API を作ると、
  `user:manage` を持たない管理者にも全アカウントが見えるため。
- **残高は履歴の合計として導出する**（残高列を持たない）。符号は各履歴が知っていて
  （加算は正・消費は負）、合計側に種別の分岐が出ない。一覧では 1 クエリでまとめて
  読み、メンバーごとに合計する。
- **PWA の名前を RewardPoints にした**（manifest / `index.html` / `app.title` /
  FastAPI の title）。Service Worker の方針は変えていない（シェルのみ precache、
  API はキャッシュしない）。JWT の issuer・audience、TOTP の issuer、
  WebAuthn の RP 名は既存トークン・登録済み認証器を壊さないため変更していない。
- マイグレーション `0004_reward_points`（3 テーブル）と
  `0005_seed_reward_points_permissions`（権限 4 件）を追加。
- ネイティブ版の JSON エクスポート／インポートは移していない。共有サーバー上の
  データになったため、端末間の持ち運び手段としての役目が無くなった。

画面は `frontend/src/pages/MembersPage.tsx`（一覧・登録）と
`MemberPointsPage.tsx`（残高・加算・消費・履歴・共有）。どちらもサーバーが返す
`access_level` で操作の出し分けを決め、ロール名では判断しない。

## 2026-07 品質ゲートの必須化（整形・静的解析・型・テスト）

CI を「Lint → Type Check → Test」の必須ゲートにした（ADR-0006）。
Backend 4 種・Frontend 4 種の計 8 ゲートで、落ちたらマージできない。
経緯は `history/2026-07-quality-gates.md`。

導入したツールと、それによって見つかった実際の不具合:

- **Ruff Format**（新規）。162 ファイル中 100 ファイルが未整形だった。一括整形した。
  `line-length` を 100 → 120 に上げ、`E501` の一律除外をやめた。
- **Ruff Check の拡張**。`select` に `C4` / `ARG` / `N` / `RET` / `PTH` / `RUF` を追加。
  `DomainException` → `DomainError`（N818）、`int(round(...))` の二重変換（RUF046）、
  未使用引数、`__all__` の未ソート、効かない `# noqa` 14 件を整理した。
- **MyPy strict**（新規）。本番コードとテストの両方を対象にし、114 件を修正。
  - `RestartWatcher` が具象 `RestartRequestStore` に依存していた **DIP 違反**を検出。
    `RestartRequestReader` Protocol を切り出し、watcher はそれだけに依存するようにした。
    テストダブルを渡すのに具象クラスの継承が要らなくなった。
  - `sessionmaker` / `dict` / `Callable` の型引数漏れ、`Result` に無い `rowcount` への
    アクセス、`FromClause.insert()`（`sa.insert(Log)` へ修正）を検出。
  - `require_permission()` が戻り値の型を持っていなかった（依存関数ファクトリ）。
- **TypeScript の追加フラグ**。`noUncheckedIndexedAccess` /
  `exactOptionalPropertyTypes` / `noImplicitOverride` /
  `noFallthroughCasesInSwitch` を有効化。空配列を前提にした `locales[0]`、
  `choices` を `string[][]` と緩く持っていた箇所（`[value, label]` のタプルへ）、
  `fetch` に `body: undefined` を渡していた箇所を直した。
- **ESLint**（新規）。`strictTypeChecked` + `react-hooks` + `sonarjs` で 74 件。
  最多は **`no-misused-promises` 19 件**で、`onSubmit={submit}` のように async 関数を
  そのままハンドラへ渡し、Promise を投げ捨てていた箇所。内部で `catch` 済みなので
  `void` で明示に変えた。`main.tsx` の非 null 断言、`response.json()` の `any`、
  `String(unknown)` による `[object Object]` の混入も直した。
- **Vitest**（新規）。Frontend にテストが 1 本も無かったため 27 件を追加
  （i18n の言語選択・プレースホルダ、テーマの OS 追従と購読解除、API クライアントの
  トークン保持とエラーコード変換、UI 設定取得のフォールバック）。
- **DDD 依存方向の検証**（新規）。`tests/unit/test_layer_dependencies.py` が AST で
  「Domain は Application / Infrastructure / Presentation を import しない」
  「Application は Infrastructure / Presentation へ依存しない」
  「Domain は FastAPI / SQLAlchemy 等に依存しない」を検証する（93 ケース）。

`make check` で CI と同じものを手元で流せる（`make format` で自動整形）。

## 2026-07 二要素認証・パスキー・テーマ切り替え・自己再起動

photonest を参考に 5 つの機能を追加し、重複していた処理を整理した。

- **二要素認証（TOTP）とパスキー（WebAuthn）** を
  `bounded_contexts/account_security/` として追加（ADR-0003）。
  移植元にあった 2 つの問題を設計で直した。
  - 共有鍵を `users` の列ではなく `totp_secrets` テーブルに置き、確認できるまで
    有効にしない 2 段階登録にした（QR の読み取り失敗で締め出されないように）。
  - WebAuthn チャレンジをプロセス内 `dict` ではなく `webauthn_challenges` テーブルに
    置いた。移植元の実装は単一プロセス専用で、既定の Gunicorn `--workers=2` では
    発行と検証が別ワーカーに当たった瞬間に必ず失敗する状態だった。
  - `pyotp` / `webauthn` は Infrastructure に閉じ込め、Domain には Protocol だけを置いた。
- **設定変更による自己再起動** を `shared/kernel/restart/` として追加（ADR-0004）。
  起動時にしか読まれない設定（`LOG_LEVEL` / `LOG_TO_DATABASE` /
  `CORS_ALLOWED_ORIGINS`）は保存しても反映されず、画面上は成功と出ていた。
  保存 API が `restart_required` を返し、`POST /api/admin/system/restart` で
  再起動を要求できるようにした。
- **テーマ切り替え**（light / dark / OS 追従）を追加。配色を CSS 変数へ移し、
  `<html data-theme>` で切り替える。以前はブラウザ任せの `Canvas` /
  `CanvasText` を使っており、アプリ側から配色を選べなかった。
- **日英切り替えの仕上げ**。`LANGUAGES` / `DEFAULT_LOCALE` は定義済みだったが
  参照するコードが無く、管理画面に並ぶだけで何も動かしていなかった。
  公開エンドポイント `GET /api/ui/settings` で配り、実際に効くようにした
  （ADR-0005）。管理画面の設定ラベル・選択肢も辞書で訳せるようにし、
  訳の抜けを `tests/unit/test_i18n_dictionaries.py` が検出する。

重複処理の整理:

- `POST /api/admin/maintenance/shutdown` を削除。自プロセスへ SIGTERM を送るだけで、
  Gunicorn 配下ではワーカーが 1 つ落ちてアービターが同じ環境で作り直すため、設定は
  反映されなかった。終了方法の判断を `build_process_terminator()` に集約し、
  `POST /api/admin/system/restart` へ一本化した。
- `system_settings` テーブルを短命コネクションで読む生 SQL が設定解決と再起動要求で
  重複していたため、`SystemSettingRecordReader` に集約した。
- アクセストークン Cookie の付与を `set_access_token_cookie()` に集約
  （パスワード・リフレッシュ・パスキーの 3 経路が同じ属性を使う）。
- `utcnow()` を `shared/kernel/timestamps.py` へ移動（Application 層からも使うため）。
- フロントエンドの 7 か所に散っていた「例外 → `error.<code>` 翻訳キー」変換を
  `errorMessageKey()` に集約した。

## 2026-07 ビルド／デプロイ最新化・PWA 対応

- ビルドを `scripts/build.sh` に集約（idp と同方式）。`dist/` に image tar・`deploy.sh`・
  `manifest.env`／`manifest.sha256`（checksum・イメージ ID 照合）を出力する。
- git 非搭載のデプロイ先向けに `scripts/build-remote-container.sh` を導入
  （dev コンテナ内で SYNC → BUILD → PICK → DEPLOY を一括実行。self-update 対応）。
- `deploy.sh` の配置を dist 直下（`<env>/deploy.sh`）に統一（旧 `<env>/scripts/deploy.sh`
  配置は廃止）。manifest による tar 検証とロード済みイメージの再利用を追加。
- DB のホスト公開ポートを既定でループバック（127.0.0.1）に限定（`DB_BIND_ADDR`）。
  公開ポートは nginx のみ。
- フロントエンドを PWA 化（vite-plugin-pwa: Web App Manifest・Service Worker 自動更新・
  アイコン一式。`/api` 等はナビゲーションフォールバック対象外）。

## 2026-07 テンプレート刷新（photonest 準拠）

- photonest の構成・設計思想をベースに全面刷新。
  DDD 4層 + bounded_contexts 構成、scope ベース認可（JWT）、
  システム設定管理（環境変数 > DB > デフォルト）、構造化ログ（JSON + DB）、
  React SPA スケルトン、Docker（db / web / nginx）、デプロイスクリプトを導入。
- アルバム・メディア・バッチ（Celery / Redis）・wiki・Google 連携は持ち込まない。
- 設計判断は ADR-0001（DB エンジン）・ADR-0002（認証スコープ）を参照。
