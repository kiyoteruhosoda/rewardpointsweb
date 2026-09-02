# Progress — 進行中タスク

進行中・未着手のタスクのみを表で管理する（完了したら本ファイルから消し、重要な変更は
`CHANGELOG.md`／`history/` へ、設計判断は `decisions/`（ADR）へ移す）。

- 状態: ⬜未着手 / 🚧進行中 / 🟡要判断
- 影響度・工数: 大 / 中 / 小

| 優先 | # | 概要 | 状態 | 影響度 | 工数 |
|---|---|---|---|---|---|
| 1 | T1 | stg の SSO・パスキーを有効にする（prod は適用済み） | ⬜未着手 | 小 | 小 |

## 詳細

1. **T1 — prod は 2026-09-02 に適用済み。** SSO とパスキーの設定はどちらも
   deploy-repo の compose で環境変数として渡している（`RPW_OIDC_*` /
   `RPW_WEBAUTHN_*` / `RPW_SESSION_COOKIE_SECURE`）。**環境変数は管理画面より
   優先されるので、`/admin/config` からは直せない**（env ロック表示になる）。

   | 環境 | SSO の client_id | 状態 |
   |---|---|---|
   | prod | `3819f1d0b2bb261cd080dd7ebe49ca7f` | 適用済み |
   | stg | `5546b7c0f63a8ea10754495918603a78` | 設定は入っているが**スタックが停止中**のため未適用 |

   prod で確認したこと: マイグレーション適用、起動ログの `sso_ready`、
   `/api/auth/sso/provider` の `enabled: true`、認可要求の送り出し（303 で idp の
   `/authorize` へ）、`sso_binding` Cookie の `Secure` / `HttpOnly` / `SameSite=lax`。

   残るのは stg で、`DeployStack rewardpointsweb-stg` を叩けば設定ごと立ち上がる。
   ただし**いま止まっているものを起こすことになる**ので、要否を決めてから行う。
   手順は `OPERATIONS.md`「外部 IdP（SSO）でログインできるようにしたいとき」。

（テンプレート刷新の経緯は `history/2026-07-template-refresh.md`、
品質ゲート導入の経緯は `history/2026-07-quality-gates.md`、
要約は `CHANGELOG.md` を参照）
