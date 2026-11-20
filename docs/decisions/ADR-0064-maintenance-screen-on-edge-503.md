# ADR-0064: 前段が 503 で閉じていると答えたら、アプリ内のメンテナンス画面に切り替える

- 日付: 2026-11-20
- 状態: 承認
- 関連: 雛形 fastapitemplate の ADR-0067（#664）の写し・nolumiatask #655（親 #653）

## 文脈

公開名の前段（edge）は、計画メンテナンスの宣言があるホストへの要求すべてに 503 を返す。deck も
`Recreate` を含む本番を配る間は自動でこの状態にする（nolumiadeck ADR-0182・#654）。
ブラウザ（`Accept: text/html`）には edge のメンテナンス画面、それ以外には JSON を返す:

```json
{"error":"service_unavailable","reason":"maintenance","until":"2026-10-28T19:30:00Z",
 "message":"<理由>","title":"<見出し>","body":"<本文>"}
```

上流（このアプリ）が居ないだけのときは `{"error":"service_unavailable","reason":"stopped","host":"…"}`。
古い edge は `title`・`body` を返さない。edge は JS・CSS にも 503（JSON）を返す。

⚠ **この画面は PWA なので、edge のメンテナンス画面は見えない。** 画面の移動では Service Worker が
手元の index.html を返す（`navigateFallback`）。これまでは配布の間、API がエラーに見えるだけだった。

## 決定

雛形の ADR-0067 と同じ振る舞いにする。

1. API の応答が 503 で、本文の**最上位**が `error: "service_unavailable"` かつ `reason` が
   `maintenance` / `stopped` なら「前段が閉じている」と読む（`frontend/src/services/maintenance.ts`）。
   アプリ自身のエラー（`{"detail": {"error": …}}`）とは形で見分ける。読むのは API の入口
   （`services/api.ts`）、最初に読む画面の設定（`services/uiSettings.ts`）。
2. 閉じている間は、アプリの画面を**消さずに隠し**、別の React の root にメンテナンスの画面を描く
   （`components/MaintenanceScreen.tsx`・`main.tsx`）。見出し・本文は edge の文言、無ければ既定の文。
   理由（`message`）と戻りの見込み（`until` を閲覧者の時間帯で、`UTC+9` の形の時間帯つき）も出す。
3. 1 分ごと・タブが手前へ戻ったとき・「いま確かめる」を押したときに `GET /api/ui/settings` で
   確かめ直す。通ればアプリの画面へ戻す（読み込み直さない＝URL も入力の途中もそのまま。認証は
   聞き直す）。ほかの API の答えが返ったときも戻す。
4. 閉じている間はエラーのトーストを出さない。ログインの聞き直し（5 秒ごと）も止める。
5. 遅れて読み込む部品が読めなかったとき（`vite:preloadError`）は、閉じているかを確かめ、
   閉じていれば同じ画面を出して、開いたら読み込み直す。ただの失敗なら何もしない。

## 雛形との違い

- 雛形の `services/localTime.ts` はこのアプリに無いので、戻りの見込みの書き方（`UTC+9` の形の時間帯）は
  `MaintenanceScreen.tsx` の中に置いた。
- 表示端末（サイネージ）が資格情報を札に換える入口（`openDisplaySession`）も同じく 503 を読む。配布の間は表示端末にもメンテナンスの画面が出る。
- このアプリの色の変数（`--surface-raised`・`--shadow-card` など）に合わせて画面の見た目を書いた。

## 理由

雛形の ADR-0067 と同じ（画面の移動は Service Worker が答えるので API の応答で切り替える・部品が
欠けても出せるよう別の root に描く・戻ったとき入力が残るよう隠すだけにする・宣言の単位に合わせて
1 分ごとに確かめ直す・部品の失敗は確かめてから決める・文言は宣言した人のものを優先する）。

## 影響

- 新しい API の入口を `api.ts` を通さずに作ると、503 を受けても切り替わらない。
- 前段が自前の 503 の形を変えたら `outageFrom` を合わせる。アプリが自分で
  `{"error":"service_unavailable","reason":"maintenance"}` を最上位に返すと、同じ画面になる。
