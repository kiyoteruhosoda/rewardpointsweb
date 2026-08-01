# CHANGELOG — 完了した重要な変更の要約

新しいものを上に追記する。細かな進捗は書かない（Progress.md 完了時に要約を移す）。

## 2026-08 ゲスト（子）の独立を実装

親メンバーが指示し、子本人が承認する 2 段階で成立する（ADR-0014）。

- **指示・取り下げ**（`POST` / `DELETE
  /api/families/{id}/memberships/{mid}/independence-proposal`）。親メンバーが、
  アカウントの結び付いた子に対して行う。承認待ちは家族の詳細応答の
  `independence_proposed` に現れる。
- **承認**（`POST /api/families/{id}/independence`）。指示を受けた子本人のみ。
  成立すると参加・台帳・記録を家族から削除し（追記専用 — ADR-0010 — の明示的な
  例外）、アカウントは所属なしの初期状態となり、ロールが `member` から
  `manager` へ昇格する。家族を作ることも招待をメンバーとして受け直すこともできる。
- `family_memberships.independence_proposed_at` を追加するマイグレーション
  （`0008_membership_independence`）。

## 2026-08 家族の所属を 1 つまでにし、脱退・解散・改名を実装

家族の運用ルール（ADR-0013）と実装が食い違っていたのを揃えた。

- **所属できる家族を 1 アカウント 1 つまでにした。** 家族の作成と招待の受諾の
  両方で検査する（`already_belongs_to_family`）。ADR-0009 が許していた複数所属と、
  それを検証していたテストを置き換えた。
- **脱退を実装した**（`POST /api/families/{family_id}/leave`）。親だけが、他に親が
  残る場合に抜けられる。owner が抜けると最古参の parent が owner を引き継ぐ。
  抜けた後は初期状態と同じで、台帳の記録は家族に残る（操作者への参照だけ外れる）。
- **解散を実装した**（`DELETE /api/families/{family_id}`）。owner のみ、自分以外の
  参加者がいない場合だけ（`family_not_empty`）。
- **改名を実装した**（`PATCH /api/families/{family_id}`）。owner のみ。

## 2026-08 アプリログの強化 — 失敗と管理操作を残し、死活監視を残さない

何かが起きたときに `log` テーブルへ十分な情報が残らず、逆に死活監視の 200 の行が
大半を占めていた。方針は ADR-0012 にまとめた。

- **失敗が記録されるようになった。** `HTTPException`・入力検証エラー・ドメイン例外は
  ルーターを抜けた先で応答へ変わるため、これまではアクセスログの 1 行
  （ステータスコードだけ）しか残らなかった。記録を
  `presentation/fastapi/error_handling.py` に集約し、`request_failed: <エラーコード>`・
  `request_validation_failed: <項目名:理由>`（**入力値は入れない**）を残すようにした。
- **管理操作を記録するようにした。** アカウントの追加・変更・削除、ロールの権限変更、
  システム設定の保存が成功しても何も残っていなかった。識別子と変更した項目名だけを
  残す（表示名・メールアドレス・設定値は残さない）。
- **失敗したログインを WARNING で残すようにした。** 従来は 401 で終わり、試行が
  続いているかが見えなかった。
- **ログのレベルをステータスコードで決めるようにした。** 5xx → ERROR、4xx →
  WARNING、401 と成功 → INFO。WARNING 以上で絞れば失敗だけが残る。
- **死活監視のパスをアクセスログから外した。** `/healthz` `/readyz` `/api/health`
  `/metrics` の成功は残さない（Docker の healthcheck が数十秒おきに叩き、`log` の
  大半を占めていた）。**失敗（4xx/5xx）は残す。**
- **識別子を本文に入れるようにした。** `log` テーブルへ入るのは列にある項目だけで、
  `extra` の残りは stdout の JSON にしか出ない。管理画面から読めない記録は残して
  いないのとほぼ変わらないため。
- **書き込みを伴うリクエストのログが SQLite で失われていたのを直した。** `get_db` は
  レスポンス送出の後に commit するため、`db.flush()` 済みのリクエストが握った書き込み
  ロックと、ログ用の別コネクションが衝突していた（busy timeout 5 秒の末に消える）。
  リクエスト中は控えに積み、処理が終わってから `DeferredLogWriteMiddleware` が
  まとめて書くようにした。管理操作の記録もアクセスログの 1 行も残るようになった。
- **500 のログ行に `user_id_hash` が乗るようにした。** `InternalErrorMiddleware` を
  素の ASGI へ変えた（`BaseHTTPMiddleware` は下流を別のタスクで走らせるため、認証
  依存関数が設定した `contextvars` が戻ってこない）。
- **パスキーのログイン失敗も WARNING で残すようにした**（パスワードのログインと同じ）。
- **システム設定の記録を、実際に採り込んだキーだけにした。** 未知のキーや伏せ字の
  ままの秘匿項目は保存されないのに「変更した」と残っていた。
- **ログ基盤自身の失敗が見えるようになった。** `DbLogHandler` は書き込み失敗を
  `handleError()`（stderr）で知らせる（従来は `pass`）。設定の DB 読み取りが
  できない状態も、状態が変わったときに 1 行だけ警告する（`system_settings_unreadable`）。

## 2026-08 422 の原因が画面に出ず、応答に打ち込んだパスワードが乗っていた

前項でフォームの送信内容は直したが、「422 が続く」という報告が止まらなかった。
原因を出せない造りが残っていたため。

FastAPI 既定の入力検証エラーは `{"detail": [{"type": ..., "loc": ..., "input": ...}]}`
という**配列**で返る。SPA の `extractErrorCode`（`frontend/src/services/api.ts`）は
`{"detail": {"error": "..."}}` からコードを取り出すため配列に当てはめられず、どの項目が
どう悪くても表示は `error.unknown_error`（「エラーが発生しました。」）だけになっていた。
利用者からは原因の違う 422 が全て同じ画面に見えていた。

併せて、既定の応答は `input` として**送った値をそのまま返していた**。8 文字未満で弾かれた
パスワードやメールアドレスが平文で応答本文に乗る。ログ側は項目名と理由だけに絞って
あった（`_validation_failures`）のに、応答から漏れていた。

対応:

- `presentation/fastapi/error_handling.py` が 422 の応答を組み立てるようにした。他の失敗と
  同じ `{"detail": {"error": "validation_error", "fields": ["password"]}}` に揃え、**項目名
  だけ**を載せる（値も Pydantic の内部的な理由も出さない）。
- `errorMessageKey` が `validation_error` のとき項目ごとの文言（`error.invalid_password` 等）
  を引くようにした。辞書に無いキーが画面へ出ないよう、文言を用意した項目名だけを使う。
  文言は「どの欄か」までにし、原因は断定しない——同じ項目名を複数のスキーマが使っており
  （`code` は招待コードと認証アプリのコードの両方）、決まりもそれぞれ違うため。
- 実際に 422 を招いていた入力欄の抜けを塞いだ。`RedeemInvitationPage` のパスワード欄に
  下限（8 文字）が無く、招待コードで作るアカウントは短いパスワードを打つたびに 422 で
  跳ね返っていた。ユーザー名の 3〜255 文字も両画面へ入れた。

`error.invalid_username` の文言は文字種にしか触れていなかったので、長さの決まりも含めた。

## 2026-08 ユーザー管理画面からアカウントを作れなくなっていた（422）

`POST /api/admin/users` が常に 422 を返し、管理画面からアカウントを追加できなかった。

ADR-0011 でログイン識別子を `username` へ分け、画面に出す名前を `display_name` として
別に持たせたとき、`UserCreateRequest` には必須項目として `display_name` が入ったが、
`frontend/src/pages/UsersPage.tsx` は分割前のまま `email` / `username` / `password` /
`roles` だけを送り続けていた。FastAPI はハンドラへ入る前に弾くため、ルーター側の
409・400 の分岐には一切届いていない。

画面が原因を出せなかったのも同じ経路による。バリデーション誤りの応答は `detail` が
配列で、`{"error": "..."}` を期待する `extractErrorCode`（`frontend/src/services/api.ts`）
に合わないため、トーストは `error.unknown_error` にしかならない。

併せて、この画面ではメールアドレスが `required` のままだった。ADR-0011 で任意項目に
なっており、メールアドレスを持たない子アカウントは元から作れない状態だった。空欄なら
`null` を送るようにし、一覧にも表示名の列と、メールアドレスを持たない行の表記を足した。

`frontend/src/pages/UsersPage.test.tsx` で送信内容を検証し、スキーマとの乖離が再発
した場合に落ちるようにした。

## 2026-08 clone 直後に `docker compose up` が通るようにし、名前を `rewardpointsweb` で固定した

README・OPERATIONS には「`docker compose up -d`」と書いてあったが、実際には動かな
かった。`docker-compose.yml` は `image:` を参照するだけで `build:` を持たないため、
compose は `rewardpointsweb:latest` を registry へ探しに行って失敗する。手元で先に
`scripts/build.sh` を回すか、`.env` を作っておく（`env_file` が必須だった）必要が
あった。

build を本体へ足さなかったのは、配置先にはソースが無く、イメージは `docker load`
で入るため。代わりに `docker-compose.override.yml` に `build:` を置いた。この
ファイルは `-f` を付けずに実行したときだけ自動で読まれ、`deploy.sh` は
`-f docker-compose.yml` を明示するので配置先の挙動は変わらない（dist / イメージ
にも入らない）。

`.env` を任意にするのも同じ override で行う。本体の `env_file: [.env]` と同じパスを
長い書式（`path:` + `required: false`）で上書きすると後者が勝ち、`.env` が無くても
起動する。本体を長い書式にしなかったのは、`required:` が Compose 2.24.0 以降の機能
で、それより古い Compose（Synology の Container Manager 等）はファイルを読み込む前に
弾くため。配置先が使うのは本体だけなので、Compose の版を選ばない短い書式のまま残した。

compose プロジェクト名は無指定だと配置ディレクトリ名になり、リポジトリを別名の
ディレクトリへ clone しただけでコンテナ・ネットワークの名前が変わっていた。
`name: rewardpointsweb` を明示して固定した。`deploy.sh` が渡す
`-p <アプリ名>-<環境>` の方が優先されるため、「配置場所がデプロイの名前を決める」
方針（stg / prod の同居）はそのまま。

`mnt/`（`HOST_DATA_ROOT` の既定値。DB のデータ実体）を `.gitignore` と
`.dockerignore` へ追加した。手元で起動すると作られるため、そのままではビルド文脈
へ数 GB が入る。

## 2026-08 本番（MariaDB）でマイグレーション `0007_family_point_ledger` が落ちていた

デプロイが `Cannot drop index 'ix_point_entries_member_id': needed in a foreign key
constraint`（MariaDB エラー 1553）で失敗していた。`point_entries.member_id` は
`members.id` への外部キーで、InnoDB はその索引を単独で落とさせない。

原因は「テーブルを落とす前に索引を落とす」という不要な手順。`DROP TABLE` は索引も
一緒に消すため、`drop_index()` は元から要らなかった。開発・テストの SQLite は同じ
DDL を通してしまうので、既存のマイグレーションのテストでは検出できていない。

`0001` / `0003` / `0004` / `0007` から、直後に `drop_table()` する表への
`drop_index()` を削除した。再発は `tests/unit/test_migration_index_drops.py` が
AST で検査する（同じ関数内で同じ表を `drop_index` と `drop_table` の両方に渡して
いたら落とす）。表を残したまま索引を張り替える `drop_index` は妨げない。

## 2026-08 家族を共有単位にし、台帳を追記型にし、子どもがログインできるようにした

主用途が「子どもへのポイント付与」に定まったことで、共有・履歴・認証の 3 つを
まとめて置き換えた（ADR-0009 / ADR-0010 / ADR-0011）。本番稼働前のため移行
スクリプトは作らず、スキーマごと入れ替えている（`0007_family_point_ledger`）。

**共有をやめて家族への参加にした（ADR-0009）。** メンバーを 1 人ずつ他のアカウント
へ共有する方式（ADR-0007）は、親 2 人 × 子 3 人で共有設定が 6 通りになり、子どもが
増えるたびに全ての親へ共有し直す運用になっていた。`Family` を集約ルートとし、
共有は家族への参加でのみ表す形に変えた。認可は家族の中での立場（owner / parent /
child）で決め、判定は `domain/services/family_access_policy.py` の 2 関数
（`can_view_ledger` / `can_modify_ledger`）に集約した。兄弟の残高・履歴は相互に
参照できない。scope も `member:*` → `family:*` へ改めた。

**台帳を追記型にした（ADR-0010）。** これまで履歴の訂正は行の削除で行っていたが、
子どもの側からは記録が黙って書き換わったように見える。動機づけを目的とする
システムで台帳への信頼が失われる影響は大きいため、`point_transactions` を追記専用
（UPDATE / DELETE をしない）にし、訂正は逆符号の行を足して `reversal_of_id` で対応
を示す形にした。`reversal_of_id` は UNIQUE なので二重取り消しは DB でも防がれる。
加算・消費は符号で区別し、残高は `SUM(amount)` で毎回導出する。マイナス残高は
許容する（前借り）。モバイルでの二重タップ対策として `idempotency_key` を必須にし、
`UNIQUE (ledger_id, idempotency_key)` の衝突はエラーにせず既存レコードを返す。

**ログイン識別子をメールアドレスから分離した（ADR-0011）。** 子どもは年齢によって
メールアドレスを持たず、保護者の管理下にない外部メールサービスの利用を前提にする
のも望ましくない。`users.username` を UNIQUE な識別子とし、`email` を nullable に
した。表示名はそれまで `username` だった列を `display_name` へ移してある。移行では
既存アカウントの `username` にメールアドレスの値を入れるので、ログインの手順は
変わらない。

子アカウントは子ども自身では作れない。親が参加を作り、招待コード（ハッシュ化して
保存し、平文は発行時に 1 度だけ返す）を渡した場合にのみ作成できる。パスワードを
忘れた場合の回復は家庭内で完結させ、親が一時パスワードを発行する。発行できるのは
同一家族の `role = child` に対してだけで、親から親へのリセットは許可しない。一時
パスワードでのログイン後は、変更を終えるまで他の操作を許可しない（サーバー側の
関門は `get_active_principal`、画面側は `RequireAuth`）。

家族の構成を変える操作（招待・除名）は owner に限り、子の追加と記録は parent にも
許す。届かない相手への応答は **403 に揃えた** — 「所属していない」「立場が足りない」
「他家族のものだった」を呼び出し元から区別させないため。存在しない家族 ID でも同じ
403 になるので、この応答から家族の実在は分からない。

**パスワード再設定の申し込みをユーザー名で行うようにした。** メールアドレスが任意
項目になり、それを起点にできなくなったため。メールアドレスを持たないアカウントには
`ask_guardian` を返し、親からの一時パスワード発行へ誘導する。この応答は「そのユーザー
名は実在し、メールアドレスを持たない」ことを意味するが、家庭内で使う識別子（親が決めて
本人へ伝える）であることを踏まえて許容した。

**加算・消費の理由に入力候補を出すようにした。** その家族で使われた理由を頻度順に
返す（`GET /api/families/{id}/reason-suggestions`）。他家族の理由は混ざらない。

**自分の表示名とメールアドレスを変えられるようにした。** `PUT /api/auth/me` を追加
し、プロフィール設定の画面から変更する。ログイン識別子（`username`）はここでは
変えない — 変えるとログインの手順が変わり、家族から本人へ伝えた ID とも食い違う。
メールアドレスは空にすると外れる（通知とパスワード再設定にのみ使う任意項目）。

なお、マスタデータを投入する既存のマイグレーション（0002 / 0005 / 0006）は ORM
モデル経由の書き込みをやめ、そのリビジョン時点のスキーマを写した Core のテーブル
定義に置き換えた。モデルは後のリビジョンで変わるため、モデル経由で書くと過去の
リビジョンを適用する途中でまだ存在しない列を参照して落ちる。

## 2026-07 ログインできない原因を切り分けられるようにし、アプリ名を自分のものにした

「ログインできない」という報告の画面には `unknown_error` の文言（「エラーが発生
しました。」）だけが出ていた。パスワード違いなら `invalid_credentials` の文言が出る
はずで、実際にはサーバー側の例外（HTTP 500）が起きていたが、画面からもログからも
それが分からなかった。原因は 3 つあり、それぞれ直した。

**1. 想定外の例外が読めない応答になっていた。** ハンドラが無いと Starlette は
本文 `Internal Server Error` の **text/plain** を返す。API クライアント
（`frontend/src/services/api.ts`）は本文を JSON として読むため、パースに失敗して
コードを取り出せず、どんな障害も一律 `unknown_error` になっていた。最後の受け皿
を足し、`{"detail": {"error": "internal_error"}}` の JSON・`X-Request-Id` ヘッダー・
traceback つきのログに揃えた。例外の中身は応答に出さない（追跡は `requestId` で行う）。

受け皿は 2 段にしてある。通常の経路は最も内側のミドルウェア
（`presentation/fastapi/middleware/internal_error.py`）で、CORS とリクエストログの
**内側**で応答へ変える。`Exception` ハンドラ（`presentation/fastapi/error_handling.py`）
だけに頼ると、Starlette がそれを全ミドルウェアの外側の `ServerErrorMiddleware` へ
載せるため、別オリジンのフロントエンドでは `Access-Control-Allow-Origin` が付かず
ブラウザが本文を捨て、結局 `unknown_error` に戻ってしまう。500 がアクセスログに
残らない問題も同時に解消した。ハンドラのほうはミドルウェア自身が落ちたとき用の
保険として残している。

**2. 初期管理者のパスワードが `admin` で、締め出されると戻せなかった。** 既定を
メールアドレスと同じ `admin@example.com` に変更した（`shared/domain/auth/master_data.py`）。
投入は冪等で既存の管理者に触れない設計だったため、既定値のままの環境が新しい既定値へ
追随できず、パスワードを忘れると復旧手段も無かった。

- 既定値のまま（`SUPERSEDED_ADMIN_PASSWORD_HASHES` に一致）の管理者だけを新しい既定値
  へ追随させる（`migrations/versions/0006_default_admin_password.py`）。運用者が自分で
  決めたパスワードには触れない。
- 明示したときだけ戻す復旧経路として `scripts/seed_master_data.py --reset-admin-password`
  を追加した（手順は OPERATIONS.md）。
- 平文とハッシュの食い違いは `tests/unit/test_master_data.py` が検出する。ドキュメント
  どおりに入れてもログインできない、という状態を機械で防ぐ。

**3. 元テンプレートと同じ名前（`fastapitemplate`）を名乗り続けていた。** イメージタグ・
compose プロジェクト名・DB コンテナ名・ネットワーク名がすべてこの名前から導かれるため、
元テンプレート由来の別プロジェクトを同じホストで動かすと、同じ `container_name` と
ホストポートを奪い合う。過去 2 回の deploy 修正（ネットワークの重複、他プロジェクトの
コンテナの切り離し）はこの衝突の症状だった。

改名だけでは「衝突しうる構造」が残る（次に名前が当たったらまた同じことが起きる）ため、
**`deploy.sh` の置き場所からデプロイの名前を決める**方式にした。アプリ名は親ディレクトリ
名、環境は自分のディレクトリ名から取る（`<アプリ名>/<stg|prod>/deploy.sh`）。別のアプリは
別のディレクトリに置かれる以上、名前は構造的に衝突しない。環境名を `basename` で決めて
いたのと同じ考え方を、アプリ名へも広げた形になる。ディレクトリ名は docker の識別子として
使うため小文字英数と `-` `_` へ正規化し、使えないときだけ `.env` の `APP_NAME` で明示する。

スクリプトに残した `BUILD_APP_NAME`（`rewardpointsweb`）は「デプロイの名前」ではなく
「`image.tar` の中身がどう tag されているか」で、`manifest.env` が無いときの load 後の
参照先にだけ使う。

旧名からの移行として、`deploy.sh` は旧アプリ名の compose プロジェクトを一度だけ畳み、
自動生成した `.env` の旧既定名を書き換える。畳む対象は compose の
`com.docker.compose.project.working_dir` ラベルがこの環境ディレクトリと一致するコンテナ
だけで構成されているときに限る。プロジェクト名ラベルの絞り込みは docker デーモン全体を
見るため、それだけを根拠にすると同じ名前を使う**別のアプリ**を停止・削除してしまう
（共存のための変更で共存相手を壊す）。永続データはホスト側の `HOST_DATA_ROOT` にある
ため、この入れ替えで消えない。

`ACCESS_TOKEN_ISSUER` / `ACCESS_TOKEN_AUDIENCE` も改名したので、**発行済みの JWT は
すべて無効になる**（`iss` / `aud` を検証しているため）。全員が一度ログインし直す。
パスキーの結び付け先である `WEBAUTHN_RP_ID` は変えていないので、登録済みのパスキーは
そのまま使える。

## 2026-07 画面を家族向けに整理し、システム関連をプロフィール設定へ寄せた

管理者は親（家族）であって運用エンジニアではないのに、ホームが「管理ダッシュボード」
で API ドキュメントへのリンクを出し、ナビゲーションにはテンプレートの見本
「アイテム」やシステム管理（ユーザー・ロール・権限・設定・ログ）が並んでいた。

- **ホーム**（`frontend/src/pages/DashboardPage.tsx`）: メンバーごとの残高カードを
  並べる家族向けの画面にし、API ドキュメント等のシステム情報を消した。
- **アイテムを画面から外した**。`bounded_contexts/example/` は開発用の最小構成の
  見本（CLAUDE.md 参照）で、家族ポイントの機能ではないため。バックエンドの見本
  自体は残している。
- **プロフィール設定**（`frontend/src/pages/ProfilePage.tsx`）: アカウント・表示設定
  （言語・テーマ）・セキュリティに加え、システム管理の入口を scope を持つ人にだけ
  ここで見せる。Sidebar には日常で使う画面（ダッシュボード・ポイント・プロフィール
  設定）だけを並べる。技術情報だった scope の一覧表示もやめた。
- **見た目の刷新**（`frontend/src/index.css`）: 面を 3 段（背景・カード・差し込み）に
  分け、影と角丸を付けたカード基調へ。送信ボタンはアクセント色の塗り、ナビの選択中
  はアクセントの淡色で示す。引き出し・セーフエリア・焦点管理の挙動は変えていない。

## 2026-07 パスワードの入力欄に中身を見せる切り替えを付けた

伏せ字のままでは打ち間違いに気付けず、ログインが通らない理由が「パスワードが違う」の
か「打ち間違えた」のか利用者に判別できなかった。とくに記号混じりの長いパスワードを
スマートフォンのソフトキーボードで打つと外しやすい。

入力欄の右端に目のボタンを置き、押すたびに `type` を `password` ↔ `text` で入れ替える
`PasswordField`（`frontend/src/components/PasswordField.tsx`）を追加し、パスワードを
入力する 4 画面すべてを差し替えた（ログイン・パスワード変更・パスワードリセット・
ユーザー追加）。

- 表示状態は部品の中だけに持つ。画面を移れば必ず伏せ字へ戻り、見せたままにはならない。
- 送信に成功した画面は入力欄を空へ戻す（部品は置かれたまま）。表示にしたままだと次に
  打つパスワードが最初から見えてしまうので、値が空へ**変わった時点**で伏せ字へ戻す。
  「空かどうか」で判定すると、何も打っていない欄で先に表示を押せなくなる。
- ボタンは `<label>` の外に置く。中に入れると押した先で入力欄まで反応してしまう。
- 読み上げ向けの `aria-label` は「押すと何が起きるか」（表示する／隠す）にし、
  切り替えに合わせて入れ替える。
- 見出しと入力欄は `useId()` の id で結ぶ。同じ画面に 2 つ並べても（パスワード変更）
  見出しが混ざらない。
- 見出しを置けない横並びのフォーム（ユーザー追加）では `placeholder` を使う。

## 2026-07 アイコンを差し替えてもデプロイ後に変わらないのを直した

`scripts/generate_app_icons.py` で絵柄を作り直してデプロイしても、ブラウザでも
インストール済みの PWA でも古いアイコンのままだった。

原因は 2 つ。

1. **参照 URL が変わらなかった**。`public/` のアイコンはファイル名が固定で、
   `index.html` と manifest もその名前を直接指していた。中身だけが変わっても
   URL が同じなので、ブラウザは手元のアイコンを使い続ける。インストール済みの
   PWA はさらに悪く、manifest の中身が 1 バイトも変わらないため、ランチャーは
   「アイコンは変わっていない」と判断して取りに行くきっかけすら持たなかった。
2. **配信側がキャッシュの指示を出していなかった**。`presentation/fastapi/routers/spa.py`
   は `FileResponse` を返すだけで `Cache-Control` を付けていなかった。指示が無いと
   ブラウザは自前の推測でキャッシュ期間を決める（ヒューリスティック・キャッシング）ため、
   アイコンだけでなく `index.html` や `sw.js` まで古い版が残り得た。
   `ETag` は付いていたが条件付きリクエスト（`If-None-Match`）を見ておらず、
   問い合わせても必ず全文を返していた。

修正:

- ビルド時に画像の中身から版を作り、`index.html` と manifest の参照に `?v=` として
  付ける（`frontend/vite.config.ts`）。絵柄が変われば URL も変わるので、端末は
  新しい絵を取りに来る。版は自動で決まり、手で書き換える箇所は無い。
- 配信に `Cache-Control` を付けた。`assets/` 配下（Vite が内容ハッシュ付きの名前で
  書き出すもの）は `immutable`、それ以外（`index.html`・`sw.js`・manifest・アイコン）は
  `no-cache` にする。
- `If-None-Match` が一致したら 304 を返し、本文を送らないようにした。`no-cache` は
  「毎回問い合わせる」であって「毎回落とす」ではない。
- アイコンを Service Worker の precache から外した（`workbox.globIgnores`）。参照が
  版付き URL になり precache の登録名と一致しなくなったため、置いても使われないまま
  更新のたびに 110KB を落とすだけになる。precache は 331KB → 225KB。

iOS にインストールした PWA だけは、ホーム画面に追加した時点のアイコンが端末に
焼き付くため配信側では直せない（削除して追加し直す）。開き方ごとの反映は
`OPERATIONS.md`「アプリのアイコンを変えたいとき」。

## 2026-07 デプロイが `network ... is ambiguous` で止まるのを直した

本番の `./deploy.sh reset` が
`Error response from daemon: network fastapitemplate-prod is ambiguous (2 matches found on name)`
で失敗し、コンテナが 1 つも起動しなくなった。

原因は 2 つが重なったこと。

1. **`docker compose down` の失敗を握り潰していた**。停止済みのコンテナを止めようとして
   `No such container` になると down はそこで中断し、ネットワークを消さずに終わる。
   スクリプトは `|| true` で無視して次へ進んでいた。
2. **docker daemon はネットワーク「名」の一意性を保証しない**（一意なのは ID だけ）。
   残ったネットワークがあるまま `up` が同名のものをもう 1 つ作ると、以降そのネットワークは
   名前で参照できなくなり、コンテナの起動が必ず失敗する。名前で `docker network rm` する
   復旧すらできない状態になる。

修正:

- `down` が失敗したら、プロジェクトのコンテナ（`com.docker.compose.project` ラベル）を
  `docker rm -f` してから `down` をやり直す。ネットワークを残したまま先へ進まない。
- `up` の前に同名ネットワークの重複を検査し、あれば全部削除して compose に 1 つだけ
  作り直させる。ネットワークは永続データを持たないので消して差し支えない。ただし
  このプロジェクト以外のコンテナが繋がっているときは触らない（切り離すとそのコンテナは
  動いたまま通信できなくなり、`up` でも復旧しないため。保守用のコンテナをこの
  ネットワークへ繋ぐ運用が OPERATIONS.md にある）。該当コンテナ名を出して終了する。
- それでも `up` が `is ambiguous` で落ちた場合（compose 側の競合で二重に作られた場合）は、
  同じ掃除をして 1 度だけ再試行する。解消できなければ、手で消す手順を示して終了する。
- 失敗時に `up` の出力を `tee` と `cat` で二重に出していたのをやめた。

手動の復旧手順は `OPERATIONS.md`「デプロイが `network ... is ambiguous` で失敗したとき」。

## 2026-07 スマートフォン向けの画面調整とアプリアイコンの刷新

画面は 48rem を境に振る舞いを変えるようになった。狭い画面では左のナビゲーションが
画面外から滑り出す引き出しになり、ヘッダーの `☰` で開く（項目を選ぶ・背景に触れる・
Escape のいずれでも閉じる）。DOM は広い画面と同じ 1 つで、開いているかどうかだけを
状態として持つ。

- **表は横に送る**。`.table-scroll` で表だけをスクロールさせ、ページ全体が横に
  動かないようにした（列を落として縦積みにする案は、履歴の「いつ・何・増減」が
  並んで見えなくなるため採らなかった）。
- **セーフエリアを避ける**。`viewport-fit=cover` で画面いっぱいに描き、ノッチ・
  ホームインジケータの領域は `env(safe-area-inset-*)` で個別に空ける。この余白は
  画面幅に関わらず入れる（`viewport-fit=cover` は全幅で効くため。横向きのノッチ付き
  端末は CSS 幅が 48rem を超えるが、切り欠きは左右に来る）。
- **引き出しを開けているあいだはキーボードの焦点を中に閉じ込める**。開くと先頭の
  項目へ移り、Tab は引き出しの中を巡回し、閉じると開閉ボタンへ戻る。背景に隠れた
  操作子へ Tab で入れると、キーボードと支援技術の利用者だけが迷子になるため。
- **指で押す的を 44px 以上にする**。狭い画面では `button` / `input` / `select` に
  `min-height: 2.75rem` を掛ける。入力欄の文字は 16px を下回らない
  （下回ると iOS がフォーカス時に画面を拡大する）。
- **高さは `dvh`**。モバイルブラウザのアドレスバーの出入りでレイアウトが飛ばない。
- **言語・テーマの切り替えを `/profile` へ移した**。選択肢の文字数で幅が決まる
  `<select>` が 2 つヘッダーにあると、狭い画面ではヘッダーが 3 行になり、本文が
  そのぶん押し下げられていた。移した先ではどちらもラベル付きで並ぶ。
- **アプリアイコンを RewardPoints のものにした**。テンプレート由来の「F」から、
  親子 4 人と、貯まったごほうびの星を描いた青いアイコンへ差し替えた。5 ファイルは
  `scripts/generate_app_icons.py` が SVG・PNG とも同じ座標から生成する（手で編集
  しない）。ランチャー側で切り抜かれる `maskable` は、角丸のアイコンを流用せず、
  端まで塗って図柄をセーフゾーン（内側 80%）に収めた専用画像
  （`pwa-maskable-512x512.png`）を用意した。
  併せて `theme_color` と `<meta name="theme-color">` をアイコンと同じ青
  （`#1c80fa`）にした（起動画面・ステータスバーの色。画面の中の accent は
  従来の `#4f46e5` のまま）。

## 2026-07 Backend の設計品質基準を Ruff で機械検証する

「関数長 30 行以下・引数 3 個以下・複雑度 10 以下」といった定量基準は、これまで
Backend では誰も測っていなかった。Ruff の該当ルールを必須ゲートに加えた（ADR-0008）。

| ルール | 見るもの | 値 |
|---|---|---|
| `C901` | 複雑度 | 10 |
| `PLR0912` | 分岐の数 | 8 |
| `PLR0915` | 文の数（関数長の代替） | 30 |
| `PLR0913` | 引数の数 | 5 |

計測したところ、複雑度・分岐・文の数は開発標準の値でそのまま全件通った（違反 0 件）
ため、緩めずにその値で固定した。落ちるのは引数だけで、閾値 3 では 36 件が落ちる。
`PLR0913` はキーワード専用引数も FastAPI の `Depends()` も 1 個として数えるため、
読みやすさを損なっていない箇所まで巻き込む。上限は 5 とし、開発標準の「3 個以下」は
位置引数に対するレビュー観点として残した。

- 既存コードの修正は 1 件。`SqlPointEntryRepository._add`（6 引数）を、
  「まだ ID を持たない履歴」を表す `_NewEntry` にまとめて 1 引数にした。
- ネスト深度（`PLR1702`）と位置引数の数（`PLR0917`）は、まさに欲しい基準を見るが
  Ruff の preview 扱いのため見送った。必須ゲートを preview の上には置かない
  （安定版へ入り次第 `Progress.md` の T4 で入れ直す）。

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
