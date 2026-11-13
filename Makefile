# ================================
# rewardpointsweb Makefile
# ================================

.PHONY: image \
	check check-backend check-frontend \
	format format-backend format-frontend \
	lint typecheck test \
	lint-frontend typecheck-frontend test-frontend

# --------------------------------
# Image (for local checks)
# --------------------------------
# Production artifacts are built by deck's build and pushed to the registry (ADR-0028).
# This target only checks locally that the Dockerfile is not broken.
IMAGE ?= rewardpointsweb:dev

image:
	bash scripts/generate_version.sh
	docker build -t $(IMAGE) .

# --------------------------------
# Quality gate (same order and commands as CI)
# --------------------------------

check: check-backend check-frontend

check-backend:
	uv run ruff format --check .
	uv run ruff check .
	uv run ruff check --preview --select PLR1702,PLR0917 .
	uv run mypy
	uv run pytest

check-frontend:
	cd frontend && npm run format:check
	cd frontend && npm run lint
	cd frontend && npm run type-check
	cd frontend && npm run test

# To run individual checks
lint:
	uv run ruff check .
	uv run ruff check --preview --select PLR1702,PLR0917 .

typecheck:
	uv run mypy

test:
	uv run pytest

lint-frontend:
	cd frontend && npm run lint

typecheck-frontend:
	cd frontend && npm run type-check

test-frontend:
	cd frontend && npm run test

# --------------------------------
# Auto-format (run before committing)
# --------------------------------

format: format-backend format-frontend

format-backend:
	uv run ruff format .
	uv run ruff check . --fix

format-frontend:
	cd frontend && npm run format
