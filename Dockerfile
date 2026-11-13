# ===== frontend build stage =====
# Node / node_modules are only used for the build, so they are not in the final image.
FROM node:26-slim@sha256:5adad64f9a1fca2d51972caa65983634c8a774eb300d72b20f7f2a0f60368072 AS frontend-builder

WORKDIR /app/frontend
COPY frontend/package*.json ./
RUN npm ci
COPY frontend/ ./
RUN npm run build

# ===== application image =====
FROM python:3.15-slim@sha256:f786b2e19cf9bb54e96bfcd4c1b40c4c56336c22e60607ffd4b080ae5b5dee83

EXPOSE 8000

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

RUN apt-get update && apt-get install -y \
    curl \
    procps \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

# uv (dependency management). Keep dependencies in a separate layer so the cache works.
# ⚠ Pin the version. With `:latest` the resolver version can change even for the same commit.
#   Keep it the same as CI (setup-uv's version).
# ⚠ **Do not COPY from the ghcr.io image.** Install from the PyPI wheel so the image
#   build does not depend on GitHub (task #172).
# uv is only needed to install dependencies, so put it in /tmp and remove it in the same RUN
# (it does not stay in the final image).
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

# Version info (shared/kernel/version.json) is **generated before the build and placed in the context**.
#
# ⚠ Passing it via build-arg was dropped (ADR-0028). .dockerignore excludes .git, so
#   git is not available inside the Dockerfile. The build's version-stamping stage
#   (pre_build: true in deploy-repo's resources/build-matrix.json) runs
#   scripts/generate_version.sh, and its output is COPYed in here.
# This RUN only marks the version as dev when the file is missing; it never rewrites existing content.
RUN bash scripts/generate_version.sh

RUN chmod +x /app/scripts/entrypoint.sh
RUN adduser -u 5678 --disabled-password --gecos "" appuser && chown -R appuser /app
USER appuser

# The entrypoint is baked into the image. compose only selects the mode via command.
ENTRYPOINT ["/app/scripts/entrypoint.sh"]
CMD ["web"]
