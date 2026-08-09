# reward_points — 家族とポイント台帳

家族（`Family`）を集約ルートとし、そこに属する子どものポイント台帳と、その
加算・消費の記録を扱うコンテキスト。

共有は **家族への参加** によってのみ表現する。メンバー単位の個別共有は持たない
（ADR-0009）。子ども本人もアカウントを持ち、`role = child` の参加者として家族に
所属する。

## 構成

```
domain/          家族・参加・台帳・記録と、立場による認可／残高の決め方
application/     ユースケース（家族・招待・台帳）とアクセス解決
infrastructure/  SQLAlchemy モデルとリポジトリ
presentation/    API ルーター・スキーマ・依存の組み立て
```

API 仕様は Swagger UI（`/docs`）・`/openapi.json` を参照（手書きしない）。

## 認可

二段。詳細と理由は ADR-0009。

1. **scope** — `family:view` / `family:manage` / `point:view` / `point:manage`。
   エンドポイントに `require_permission(...)` で宣言する。
2. **家族の中での立場** — `owner` / `parent` / `child`。
   `domain/services/family_access_policy.py` が唯一の判定者。

| role | 家族の管理（招待・除名） | 子の作成 | 加算・消費・訂正 | 閲覧 |
|---|---|---|---|---|
| owner | ○ | ○ | 全ての子 | 全ての子 |
| parent | × | ○ | 全ての子 | 全ての子 |
| child | × | × | × | 自分の台帳のみ |

兄弟の残高・履歴は相互に参照できない。1 つのアカウントが複数の家族へ所属できるが、
同一家族では 1 アカウント 1 参加（`UNIQUE (family_id, account_id)`。DB 制約に頼らず
アプリケーション層でも断る）。

届かないときは **403**（`family_access_denied`）で揃える。「所属していない」
「立場が足りない」「他家族のものだった」を呼び出し元から区別させない。存在しない
家族 ID でも同じ 403 になる（参加が引けない、という同じ結末を辿る）。台帳だけは、
そもそも行が無い場合に 404（`ledger_not_found`）。すべてのユースケースは
`FamilyAccessResolver` を通してから対象を触る。

判定が散らかっていないことは `tests/unit/test_reward_points_invariants.py` が
AST で見る（`FamilyRole` を比較してよいのはポリシーと変換の層だけ）。

## 台帳

`point_transactions` は **追記専用**。UPDATE も DELETE も行わない（ADR-0010）。

- 加算と消費は **符号** で区別する（`amount` は 0 以外の符号付き整数）。
- 残高は保持せず `SUM(amount)` で導出する（`LedgerStatement`）。有効期限・期間
  リセットが無いため、集計対象は常に台帳の全レコード。
- **マイナス残高を許容する**（前借りの運用）。消費時の残高検証は行わない。
- 打ち消しは元レコードの逆符号の行を追加し、`reversal_of_id` で対応を示す。
  `reversal_of_id` は UNIQUE なので二重取り消しは DB でも防がれる。打ち消しレコード
  自体は打ち消せない（`reversal_of_reversal_not_allowed`）。
- 加算・消費の API は `idempotency_key` を必須とする。`UNIQUE (ledger_id,
  idempotency_key)` に抵触した場合はエラーとせず既存レコードを返す。

### 訂正（入力の間違いを直す）

打ち消して正しい内容を書き直す操作を 1 つにまとめたもの（ADR-0022）。
`.../transactions/{id}/corrections` へ訂正後の内容を送ると、1 つのトランザクションで
2 行が足される。

| 足す行 | 参照 |
|---|---|
| 打ち消し | `reversal_of_id` = 元の行 |
| 訂正後 | `corrects_id` = 元の行（NULL 可・UNIQUE・`ON DELETE SET NULL`） |

- `occurred_at` を省くと元の行の発生日時を引き継ぐ（量を直しただけで出来事が
  今日へ動かない）。日付そのものを直したいときは指定する。
- 打ち消しの行は訂正できない（409 `correction_of_reversal_not_allowed`）。
  すでに打ち消された行も訂正できない（409 `transaction_already_reversed`）。
  訂正後の行はさらに訂正できる。
- 送り直しは打ち消しの UNIQUE に当たって 409 になる。二重には効かない。
- 1 回の訂正が 2 行を書くため、鍵は `IdempotencyKey.for_step` で段階ごとに分ける。
  受け取る鍵の上限は分けた後も収まる長さ（`MAX_BASE_LENGTH`）まで。区切り文字
  （`#`）は分割の予約で、クライアントの鍵には使えない（全 API で 422）。
  同じ鍵を別の記録の訂正へ使い回した場合は 409 `idempotency_key_reused`。

`occurred_at`（出来事の発生日時。遡って入力できる）と `created_at`（レコード作成
日時）は別物。どちらも UTC。一覧は `occurred_at` の降順（同値なら `id` の降順）。

`GET /api/families/{id}/reason-suggestions` が、その家族でよく使われた理由を頻度順に
返す（入力候補）。他家族の理由は混ざらず、打ち消しは数えない（元の理由を引き継ぐため
二重に効いてしまう）。訂正で言い直された理由も数えない（直したはずの書き間違いを
選び直さないため）。理由の文言は他の子の記録から来ることがあるので、親にだけ返す。

## 参加の追加

`family_invitations` の招待コード（ハッシュ化して保存。平文は発行時に 1 度だけ
返す）で行う。入り口は 2 つある。

| 経路 | 認証 | 用途 |
|---|---|---|
| `POST /api/families/invitations/accept` | 要 | すでにアカウントを持つ人が加わる |
| `POST /api/families/invitations/redeem` | 不要 | 招待コードでアカウントを作って加わる |

`role = child` の招待では、親が先に作った参加者を `target_membership_id` で指す。
子が受諾した時点でアカウントと結び付く。子アカウントの作り方はこの経路だけで、
子ども自身では作れない（ADR-0011）。

配れるのは `parent` と `child` だけ（`role_not_invitable`）。`owner` を配ると、
受け取った人が元の owner を除名して家族を乗っ取れる。

**1 回きりであることは「参加を作る前に使用済みにする」で担保する。** 引いてから
使用済みにする 2 手に分けると、同じコードで同時に届いた 2 つの要求がどちらも
「まだ使える」と判断してしまう。以降の検証で弾かれた場合はトランザクションごと
巻き戻るので、使えるはずのコードが無駄に消えることもない。

## 一時パスワード

メールアドレスを持たないアカウントでは SMTP 経由のリセットが成立しないため、
親が一時パスワードを発行する（`POST /api/families/{id}/memberships/{id}/password-reset`）。

- 対象は同一家族の `role = child` に限る。親から親へのリセットは許可しない。
- 発行された一時パスワードには有効期限がある（`TEMPORARY_PASSWORD_TTL_SECONDS`）。
- 一時パスワードでのログイン後は、パスワードの変更を完了するまで他の操作を許可
  しない（`users.must_change_password`。関門は `get_active_principal`）。
- 発行の事実は構造化ログと `log` テーブルに残る。

## アカウントを削除するとき

| 参照 | 挙動 |
|---|---|
| 家族の owner として残っている | 削除を拒む（409 `user_still_owns_families`） |
| 家族に参加していた | 参加と台帳は残り、アカウントの紐付けだけが外れる |
| 台帳へ記録していた | 記録は残る（操作者が分からなくなる） |

無効化したいだけなら `is_active` を偽にする。

記録の残っている参加者は家族から外せない（409 `ledger_not_empty`）。台帳は追記
専用で消す手段を持たないため、外せてしまうと履歴が黙って消える経路になる。

## 控え（バックアップと復元）

家族 1 つを 1 つの JSON へ書き出し、そこから作り直せる（ADR-0025）。

| 操作 | 入口 | 誰が |
|---|---|---|
| 書き出し | `GET /api/families/{id}/export` | 親（owner / parent） |
| 取り込み | `POST /api/families/import` | どの家族にも所属していない親 |

控えに入るもの: 家族の名前・参加者（呼び名・立場・並び順）・子どもの台帳・記録の
全部（打ち消し・訂正の繋がりを含む）・毎日のボーナス（渡し終えた日まで）。

控えに入らないもの: **アカウント**（ログイン ID・パスワード）・未使用の招待・
DB の ID・冪等キー。

行どうしの繋がりは、DB の ID ではなくファイルの中だけで通じる `ref`（`m1` /
`t1`）で表す。復元先では ID が全部変わるため。書き出した JSON をそのまま
取り込めば元に戻る（`exported_at` だけがずれる）。

取り込みは必ず **新しい家族** を作り、呼んだ人が owner の席に就く（控えの owner の
呼び名を継ぐ）。それ以外の参加者はアカウント未紐付けで戻るので、招待コードを
その人を **指して** 配り直す。台帳の行は追記として書かれ、出来事の日時
（`occurred_at`）は控えのもの、記録された日時（`created_at`）は取り込んだ時刻になる。

中身の辻褄は `application/family_archive_rules.py` が取り込みの前に見る。基準は
「この API を順に叩けば同じ家族が作れるか」。

- owner がちょうど 1 人／台帳を持つのは子だけ、そして子は必ず持つ
- 打ち消しは打ち消せない・同じ行を 2 度打ち消せない・打ち消しは逆符号
- 訂正は打ち消しを伴う・同じ行の言い直しは 1 度だけ・打ち消しの行は訂正できない
- 記録した人は親（台帳へ書けるのは親だけ）
- 毎日のボーナスの `granted_through` が `starts_on` より前にならない
- 打ち消し・訂正の相手は、並び順でそれより前にある

合わなければ 1 行も書かずに 400（`invalid_family_archive`）。読めない版は 400
（`unsupported_archive_version`）。参加者 100・記録は控え全体で 20,000 までを
スキーマで受ける（超えたら 422）。

## テーブル

| テーブル | 用途 |
|---|---|
| `families` | 家族（集約ルート） |
| `family_memberships` | 参加。`account_id`（任意）・`role`・`display_name` |
| `point_ledgers` | 台帳。`membership_id` は一意（`role = child` と 1 対 1） |
| `point_transactions` | 記録（追記専用）。`amount` / `reversal_of_id` / `corrects_id` / `idempotency_key` |
| `family_invitations` | 招待。`code_hash`・`role`・`target_membership_id`・有効期限 |

定義の正本は `infrastructure/reward_points_models.py`。DDL の変更は Alembic で行う。
