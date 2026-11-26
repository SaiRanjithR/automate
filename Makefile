# BidReady — run `make help` for targets. See DEV_SETUP.md.

SHELL := /bin/bash
.DEFAULT_GOAL := help

# The app reads .env itself (backend/app/core/config.py); only host/port are needed here.
API_HOST ?= 127.0.0.1
API_PORT ?= 8000

BACKEND := cd backend &&
FRONTEND := cd frontend &&

.PHONY: help setup prefetch dev dev-backend dev-frontend lint format typecheck test check \
        migrate migration gen-api eval samples seed-demo demo-reset nlp-company build start clean-data

help: ## Show available targets
	@grep -E '^[a-zA-Z_-]+:.*?## ' $(MAKEFILE_LIST) | awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[36m%-14s\033[0m %s\n", $$1, $$2}'

setup: ## Install backend + frontend deps and run migrations
	$(BACKEND) uv sync
	$(FRONTEND) pnpm install --frozen-lockfile
	$(MAKE) migrate
	$(MAKE) prefetch

prefetch: ## Download the local embedding model once (~130 MB) so demos work offline
	$(BACKEND) uv run python -c "from app.pipeline.embed import FastEmbedder; FastEmbedder('BAAI/bge-small-en-v1.5'); print('Embedding model ready')"

dev: ## Run backend (:8000) and frontend (:5173) together
	@trap 'kill 0' EXIT INT TERM; \
	$(MAKE) --no-print-directory dev-backend & \
	$(MAKE) --no-print-directory dev-frontend & \
	wait

dev-backend: ## Run the API with auto-reload
	$(BACKEND) uv run uvicorn app.main:app --reload --host $(API_HOST) --port $(API_PORT)

dev-frontend: ## Run the Vite dev server (proxies /api)
	$(FRONTEND) pnpm dev

lint: ## Lint backend (ruff) and frontend (eslint, prettier check)
	$(BACKEND) uv run ruff check . && uv run ruff format --check .
	$(FRONTEND) pnpm lint && pnpm format:check

format: ## Auto-format backend and frontend
	$(BACKEND) uv run ruff format . && uv run ruff check --fix .
	$(FRONTEND) pnpm format

typecheck: ## Type-check backend (mypy strict) and frontend (tsc)
	$(BACKEND) uv run mypy app
	$(FRONTEND) pnpm typecheck

test: ## Run backend (pytest) and frontend (vitest) tests
	$(BACKEND) uv run pytest
	$(FRONTEND) pnpm test

check: lint typecheck test ## Lint + typecheck + tests (must pass before ticking a task)

migrate: ## Apply database migrations
	$(BACKEND) uv run alembic upgrade head

migration: ## Create a migration: make migration m="add x"
	@if [ -z "$(m)" ]; then echo 'Usage: make migration m="message"'; exit 1; fi
	$(BACKEND) uv run alembic revision --autogenerate -m "$(m)"

gen-api: ## Regenerate frontend API types from the backend schema (no server needed)
	$(FRONTEND) pnpm gen:api

eval: ## Score requirement extraction against samples/ (uses the configured LLM provider)
	$(BACKEND) uv run python scripts/eval_extraction.py

samples: ## Regenerate the demo tender, corrigendum and company documents in samples/
	$(BACKEND) uv run python scripts/make_samples.py

seed-demo: ## Load the demo company, knowledge base and one analysed + drafted project
	$(BACKEND) uv run python -m app.scripts.seed_demo

nlp-company: ## Generate + load the sample IT/AI company pack (for NLP/IT tenders); keeps your company name
	$(BACKEND) uv run python scripts/make_nlp_samples.py
	$(BACKEND) uv run python -m app.scripts.load_company_pack ../samples/nlp-company --apply-profile --keep-name

demo-reset: ## Wipe local data (backend/data) and reseed the demo — for rehearsals
	rm -rf backend/data
	$(MAKE) seed-demo

build: ## Build the frontend for production
	$(FRONTEND) pnpm build

start: ## Serve API + built frontend on :8000 (production mode)
	$(BACKEND) APP_ENV=production uv run uvicorn app.main:app --host $(API_HOST) --port $(API_PORT)

clean-data: ## Delete local DB, vectors and files in backend/data (asks first)
	@read -p "Delete backend/data (database, vectors, uploads)? [y/N] " answer; \
	if [ "$$answer" = "y" ]; then rm -rf backend/data && echo "Deleted backend/data"; else echo "Cancelled"; fi
