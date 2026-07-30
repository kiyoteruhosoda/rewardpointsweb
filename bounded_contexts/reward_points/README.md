# reward_points — 人ごとのポイント

メンバー（ポイントを貯める人）と、その加算・消費の履歴を扱うコンテキスト。

ログインアカウント（`users`）とメンバー（`members`）は**別物**。メンバーは
ログインできなくてもよく（小さな子どもなど）、必要なら 1 つのアカウントを
「本人」として紐付けられる。

## 構成

```
domain/          メンバー・共有・履歴と、アクセス範囲／残高の決め方
application/     ユースケース（一覧・登録・記録・共有）とアクセス解決
infrastructure/  SQLAlchemy モデルとリポジトリ
presentation/    API ルーター・スキーマ・依存の組み立て
```

API 仕様は Swagger UI（`/docs`）・`/openapi.json` を参照（手書きしない）。

## アクセス範囲

認可は二段。詳細と理由は ADR-0007。

1. **scope** — `member:view` / `member:manage` / `point:view` / `point:manage`。
   エンドポイントに `require_permission(...)` で宣言する。
2. **メンバー単位アクセス** — そのメンバーへ触れるか。`MemberAccessPolicy` が
   到達経路から決める。

| 経路 | 範囲 |
|---|---|
| 所有者（`owner_user_id`） | `manage` |
| 共有された人（`member_shares.access_level`） | 共有時に決めた範囲 |
| 本人（`linked_user_id`） | `view` のみ |

複数の経路で到達できるときは強い方を採る。どの経路も無ければ **404**
（`member_not_found`）。到達はできるが変更権が無ければ **403**
（`member_access_denied`）。

`point:manage` を持っていても、`view` で共有されたメンバーは変更できない。
すべてのユースケースは `MemberAccessResolver` を通してから対象を触る。

## 残高

残高は `point_entries` の合計として毎回導出する（残高列は持たない）。符号は各履歴
が知っていて（`PointAddition` は正、`PointConsumption` は負）、`PointLedger` は
`signed_points` を足すだけ。種別が増えても合計の式は変わらない。

消費で残高不足は拒まない。先に景品を渡してから記録する運用があり、残高は導出値
なので負の値もそのまま表せる。

履歴の訂正は行の削除で行う（打ち消しの行は作らない）。`member_id` を条件に含めて
消すため、閲覧権のある別メンバー経由で他人の履歴は消せない。

## 共有

共有先は**メールアドレス**で指定する。アカウント一覧を返す口は用意しない
（`user:manage` を持たない管理者に全アカウントを見せないため）。無効化された
アカウント（`is_active` が偽）は共有先に選べない。

- 所有者自身を共有先にはできない（`share_with_owner_not_allowed`）。
- 同じ相手への二重共有はできない（`member_already_shared`）。
- **共有の管理（一覧・追加・解除）は所有者だけ**（`MemberAccessResolver.require_ownership`）。
  `manage` で共有された相手はポイントを記録できるが、共有は配り直せない。

## アカウントを削除するとき

| 参照 | 挙動 |
|---|---|
| 登録したメンバーが残っている | 削除を拒む（409 `user_still_owns_members`） |
| 共有されていた | その共有だけ消える |
| メンバー本人として紐付いていた | メンバーは残り、紐付けが外れる |
| ポイントを記録していた | 履歴は残る（記録者が分からなくなる） |

無効化したいだけなら `is_active` を偽にする。

## メンバー本人の紐付け

`linked_user_email` を指定して登録すると、そのアカウントが本人になる。1 つの
アカウントを紐付けられるメンバーは 1 人だけ（`linked_user_id` は一意）。

本人は自分のメンバーだけが一覧に並び、残高と履歴を見られる。変更の API は
scope（`member` ロールに `point:manage` が無い）と関係（本人は `view` 止まり）の
両方で塞がれている。

## テーブル

| テーブル | 用途 |
|---|---|
| `members` | メンバー。`owner_user_id` / `linked_user_id`（一意・任意） |
| `member_shares` | 共有。`member_id` + `user_id` が主キー、`access_level` |
| `point_entries` | 履歴。`entry_type` と、加算の `reason` / 消費の `application` |

定義の正本は `infrastructure/reward_points_models.py`。DDL の変更は Alembic で行う。
