# ADR-0028: バージョン情報はビルドの前に生成してコンテキストへ入れる

- 日付: 2026-08-24
- 状態: 承認

## 文脈

`/info`・システムステータス画面・起動ログが答えるバージョンは
`shared/kernel/version.json` から来る。このファイルは `Dockerfile` の中で
`--build-arg`（`COMMIT_HASH` ほか 5 つ）から組み立てていた。手元の
`scripts/build.sh` は git から値を集めて渡すので、その経路では正しく刻まれる。

ところが**本番のイメージを焼いているのは Komodo（nolumialab）**で、Komodo は
コミット情報を build-arg で渡さない（自動で渡すのは Komodo 自身のビルド版数
`VERSION=0.0.N` だけ）。`.dockerignore` が `.git` を除いているため、Dockerfile の
中から git を引くこともできない。

結果、**本番で動いているイメージが自分の版を答えられない**。ARG の既定値がそのまま
使われて `version=dev` / `branch=unknown` になる。しかも**ビルドは成功する**ので、
壊れていることに気付く手がかりが `/info` を見に行くしかない。

## 決定

バージョン情報は **`docker build` の前に `scripts/generate_version.sh` で生成して
ビルドコンテキストへ入れる**。build-arg は廃止する。

- Komodo Build の `pre_build` がクローン済みリポジトリでこのスクリプトを実行する
  （deploy-repo `resources/builds.toml`）。
- `Dockerfile` の `RUN` は「無ければ `dev` と刻む」だけで、既にある内容は書き換えない。
- `scripts/build.sh`（手元でのバンドル作成）も同じスクリプトを呼んでから焼く。

優先順位は **git > 既にある version.json > dev**。

## 理由

- **渡す側ごとに名前がずれない。** build-arg 方式は「渡す側」（`build.sh` /
  GitHub Actions / Komodo）がそれぞれ同じ値を並べる必要があり、名前が食い違えば
  黙って既定値になる。生成する場所を 1 つにすれば食い違いようがない。
- **git が引ける場所では必ず作り直す。** Komodo はビルドディレクトリ
  （`/etc/komodo/builds/<name>`）を使い回して `git pull` するため、「既にある version.json を
  優先」にすると 2 回目以降のビルドが**初回の版を名乗り続ける**。
- **イメージの中（git が無い）では既存を絶対に上書きしない。** 上書きにすると
  `pre_build` が作った本物の版を `Dockerfile` の `RUN` が `dev` に潰す。
- 採らなかった案:
  - **Komodo 側で build-arg を埋める** — Komodo にコミット SHA を渡す仕組みが無い。
  - **`.git` をビルドコンテキストへ入れる** — `python:3.12-slim` に git を入れる必要があり、
    履歴全体をコンテキストへ送ることになる。

## 影響

- `shared/kernel/version.json` は `.gitignore` に入れた。**コミットしてはいけない。**
  コミットするとイメージの中でその内容が優先され、どのイメージも同じ古い版を名乗る。
- deploy-repo の Build 定義に `[build.config.pre_build]` が**必須**になった。
  消すとビルドは緑のまま版だけが失われる。
- 大元のテンプレート（fastapitemplate）も同じ方式へ揃えてある（あちらの ADR-0023）。
