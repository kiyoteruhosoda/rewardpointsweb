# display_devices — 表示端末（サイネージ）のペアリング

リビングの iPad などに家族の残高を出しっぱなしにする「表示端末」を、パスワードを
打たせずに入れるためのコンテキスト（ADR-0047）。持つのは 2 つだけ。

| 持ち物 | 表 | 中身 |
|---|---|---|
| ペアリング | `display_pairings` | 確認コード・端末の秘密（どちらもハッシュ）、期限、承認で生まれた表示アカウント、受け取った日時 |
| 端末の資格情報 | `display_credentials` | 表示アカウントに 1 つ。ハッシュと、最後に使った日時 |

表示アカウントそのもの（家族の参加・アカウント）は reward_points が持つ
（`application/use_cases/manage_displays.py` の `DisplayRoster`）。2 つをつなぐのは
`presentation/router.py`。

## 流れ

1. 端末が `POST /api/display/pairings` で確認コード（`KQ7M-3XPA`）と端末の秘密を受け取り、コードと QR を出す
2. 運用管理者（`display:approve`）が `POST /api/display/pairings/approve` で、確認コード・映す家族・名前を送る。
   ここで表示アカウントが生まれる
3. 端末は 5 秒ごとに `POST /api/display/pairings/claim` を端末の秘密で叩き、承認されたら端末の資格情報を 1 度だけ受け取る
4. 以後は `POST /api/display/session` で資格情報を 5 分のアクセストークンへ換える（毎回 DB を引く）

API 仕様は Swagger UI（`/docs`）・`/openapi.json` を参照（手書きしない）。

## 決まり

- 確認コードは 10 分で切れる。紛らわしい字（0/O・1/I/L）を使わない 8 字。区切り・小文字は許す
- 確認コードだけでは受け取れない（受け取りは端末の秘密）
- 期限が切れて 1 日経ったペアリングは、次にペアリングが始まったときに消える
- 資格情報は使われないまま 90 日で失効し、その表示端末は外される（参加とアカウントを消す）
- 外すと（運用管理者・家族の親）、アカウントと一緒に資格情報も消える。手元のアクセストークンは寿命（5 分）まで通る
- 表示端末のアクセストークンには `via: display_device` が載り、資格情報・プロフィールを変える経路は断られる
  （`display_device_not_allowed`）
