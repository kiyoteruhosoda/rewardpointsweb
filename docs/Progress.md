# Progress — 進行中タスク

進行中・未着手のタスクのみを表で管理する（完了したら本ファイルから消し、重要な変更は
`CHANGELOG.md`／`history/` へ、設計判断は `decisions/`（ADR）へ移す）。

- 状態: ⬜未着手 / 🚧進行中 / 🟡要判断
- 影響度・工数: 大 / 中 / 小

| 優先 | # | 概要 | 状態 | 影響度 | 工数 |
|---|---|---|---|---|---|
| 1 | T1 | 本番の `WEBAUTHN_RP_ID` を公開ドメインへ直す | ⬜未着手 | 中 | 小 |
| 2 | T2 | prod / stg の SSO を有効にする（idp のクライアント登録は済み） | 🚧進行中 | 中 | 中 |

## 詳細

1. **T1 — パスキーが本番で使えない。** `WEBAUTHN_RP_ID` が既定の `localhost` のまま
   （デプロイの環境変数でも渡していない）で、`rewardpointsweb.nolumia.com` から
   開くと必ず食い違う。直し方は `OPERATIONS.md`「二要素認証・パスキーを設定したい
   とき」——**本番の URL を開いたまま** `/admin/config` のパスキーの節で
   「いま開いている URL に合わせる」を押して保存する。DB を作り直しても戻らない
   ようにするなら、代わりに deploy-repo の compose へ `WEBAUTHN_RP_ID` /
   `WEBAUTHN_ORIGIN` を足す（そのときは画面から直せなくなる）。
2. **T2 — SSO の受け入れ側は入ったが、まだ繋いでいない。** idp 側のクライアント登録は
   2026-09-02 に済んでいる（`token_endpoint_auth_method` は `private_key_jwt`、
   鍵は nolumialab 共通の `/srv/secrets/oidc/client.key`）。

   | 環境 | issuer | client_id |
   |---|---|---|
   | prod | `https://identity.nolumia.com/01a00dfe-bffb-7f23-88b5-8bbef50d23f0` | `3819f1d0b2bb261cd080dd7ebe49ca7f` |
   | stg | 同上（stg の idp は `private_key_jwt` 未対応のため prod のテナントを向く） | `5546b7c0f63a8ea10754495918603a78` |

   残っているのは、この変更をデプロイしたうえで、
   `/admin/config`（または deploy-repo の `RPW_OIDC_*`）へ上の値を入れることと、
   `/srv/secrets/oidc/client.key` をコンテナへ read-only で渡すこと。起動ログに
   `sso_ready` が出るところまで確かめる。手順は `OPERATIONS.md`
   「外部 IdP（SSO）でログインできるようにしたいとき」。登録し直したくなったら
   `/config/rewardpointsweb-idp/register-rewardpointsweb.mjs`（冪等）。

（テンプレート刷新の経緯は `history/2026-07-template-refresh.md`、
品質ゲート導入の経緯は `history/2026-07-quality-gates.md`、
要約は `CHANGELOG.md` を参照）
