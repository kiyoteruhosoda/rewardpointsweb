# ===== frontend build stage =====
# Node / node_modules はビルドにしか使わないため、最終イメージには含めない。
FROM node:24-slim AS frontend-builder

WORKDIR /app/frontend
COPY frontend/package*.json ./
RUN npm ci
COPY frontend/ ./
RUN npm run build

# ===== application image =====
FROM python:3.14-slim@sha256:51dafde81dbdb6ebde285137a295cf18a47ca95234fe388a343719cb97305b3d

EXPOSE 8000

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

RUN apt-get update && apt-get install -y \
    curl \
    procps \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

# uv（依存管理）。依存レイヤーを分けてキャッシュを効かせる。
# ⚠ 版を固定する。`:latest` だと同じコミットからでも解決器の版が変わりうる。
#   CI（setup-uv の version）と同じ版に揃える。
# ⚠ **ghcr.io の像から COPY しない。** 像のビルドが GitHub に頼らないよう、
#   PyPI の wheel から入れる（task #172）。
# uv は依存を入れるときにしか使わないので、/tmp に入れて同じ RUN の中で消す
# （最終イメージに残さない）。
# renovate: datasource=pypi depName=uv
ARG UV_VERSION=0.12.5

WORKDIR /app
COPY pyproject.toml uv.lock ./
RUN python -m pip install --no-cache-dir --disable-pip-version-check --root-user-action=ignore \
      --target /tmp/uv "uv==${UV_VERSION}" \
    && /tmp/uv/bin/uv sync --frozen --no-dev --no-install-project \
    && rm -rf /tmp/uv

COPY . /app
COPY --from=frontend-builder /app/frontend/dist /app/frontend/dist
ENV PATH="/app/.venv/bin:$PATH"

# バージョン情報（shared/kernel/version.json）は **ビルドの前に生成してコンテキストへ入れる**。
#
# ⚠ build-arg で渡す形はやめた。Komodo Build はコミット情報を build-arg で渡さず、
#   .dockerignore が .git を除いているので Dockerfile の中から git も引けない。
#   その結果 **ビルドは成功したまま** イメージが version=dev を名乗り、/info も
#   システムステータス画面も「どのコミットが動いているか」を答えられなかった。
#   Komodo Build の pre_build が scripts/generate_version.sh を実行し、その出力が
#   ここへ COPY されてくる（deploy-repo resources/builds.toml）。
# この RUN は「無かったときに dev として印を付ける」だけで、既にある内容は書き換えない。
RUN bash scripts/generate_version.sh

RUN chmod +x /app/scripts/entrypoint.sh
RUN adduser -u 5678 --disabled-password --gecos "" appuser && chown -R appuser /app
USER appuser

# エントリポイントはイメージに焼き込む。compose は command でモードのみ指定する。
ENTRYPOINT ["/app/scripts/entrypoint.sh"]
CMD ["web"]
