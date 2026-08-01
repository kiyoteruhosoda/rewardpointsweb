# ADR-0017: 家族の作成は `family:view` で許し、保護者になった時点でロールを昇格する

- ステータス: 承認
- 日付: 2026-08-01
- 関連: ADR-0013（所属は 1 家族まで。「所属していないアカウントだけが作れる」）、
  ADR-0014（独立時の member → manager 昇格。この昇格の仕組みを再利用する）
- 対象: `bounded_contexts/reward_points/`

## コンテキスト

家族の作成（`POST /api/families`)は `family:manage` を要求していたが、この scope を
持つのは manager / admin だけで、閲覧専用ロール（member）のアカウントは家族を
作れなかった。ADR-0013 は「どの家族にも所属していないアカウントだけが、家族を
作れる（作った人が owner）」「所属の経路は『招待を受ける』か『自分で作る』の
2 つだけ」と定めており、member として登録されたアカウントが入口の scope で
締め出されるのはこのルールと噛み合わない。

同根の問題が招待の受諾にもあった。受諾（`/invitations/accept`）は `family:view` で
呼べるため、member のアカウントが親（parent）として家族へ加われるが、アプリ
ケーションロールは member のままなので、家族の中では親なのにポイントを記録
できない（`point:manage` が無い）。

## 決定

1. 家族の作成は、招待の受諾と同じく **`family:view`** で呼べる入口とする。
   「その家族を触れるか」は従来どおり所属（ADR-0013 の
   `already_belongs_to_family` 検査）が決める。
2. **保護者の立場を得た時点で、アプリケーションロールを親（メンバー）と同じ
   `manager` へ昇格する**（`grant_guardian_permissions`）。呼ぶのは次の 3 箇所。
   - 家族の作成（作った人が owner になる）— 本 ADR
   - 親（parent）としての招待受諾 — 本 ADR
   - 独立の成立 — ADR-0014（従来どおり）
3. `grant_guardian_permissions` は、保護者相当の scope（`family:manage`）を既に
   持つロールがあるアカウントには何もしない。admin が家族を作っても manager
   ロールが重なって付かない。

scope は JWT に焼き込まれているため、昇格した権限は**再ログイン後**に有効になる
（ADR-0014 と同じ）。画面は昇格が起きた操作の成立後に再ログインを促す。

## 理由

- 「所属していなければ誰でも作れる」（ADR-0013）を scope の設計に反映した。
  作成は既存の家族を管理する操作ではなく所属の入口なので、入口のもう一方
  （招待の受諾）と同じ `family:view` が適切。
- 検討した代替案: member ロールへ `family:manage` / `point:manage` を付与する。
  子アカウントも member ロールを持つため、子の操作を止める防壁が家族内 role の
  1 層だけになってしまう（現在は scope と家族内 role の 2 段構え —
  `tests/integration/api/test_families.py::test_child_cannot_modify_own_ledger`）。
  採用しない。
- 昇格を作成・受諾の時点で行うのは、owner / parent になったのに子の追加も
  ポイントの記録もできない「名ばかりの保護者」を作らないため（ADR-0014 の
  「独立が名ばかりになる」と同じ理屈）。

## 影響

- 子（member ロール）が家族の作成を試みると、scope の 403 ではなく所属の検査で
  409（`already_belongs_to_family`）になる。挙動としては従来どおり作れない。
- guest ロールは `family:view` を持たないため、従来どおり作成できない。
- 昇格直後の操作は古いトークンの scope で止まるため、画面（FamiliesPage）は
  昇格が起きたとき再ログインを促してログアウトする。
