.PHONY: help setup up down logs restart build clean lint format test \
        test-backend test-model test-alerts test-frontend migrate seed train shell-%

help:  ## Show this help
	@grep -E '^[a-zA-Z_%-]+:.*?## .*$$' $(MAKEFILE_LIST) \
		| awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[36m%-18s\033[0m %s\n", $$1, $$2}'

# ------------------------------------------------------------------ setup
setup:  ## First-time setup (env file + deps)
	@test -f .env || cp .env.example .env
	cd backend && pip install -r requirements.txt
	cd ai-model && pip install -r requirements.txt
	cd alert-system && pip install -r requirements.txt
	cd data-pipeline && pip install -r requirements.txt
	cd frontend && npm install

# ------------------------------------------------------------ docker stack
up:  ## Start the full stack
	docker compose up -d --build

down:  ## Stop the stack
	docker compose down

logs:  ## Tail all service logs
	docker compose logs -f

restart:  ## Restart the stack
	docker compose restart

build:  ## Rebuild all images
	docker compose build --no-cache

clean:  ## Stop stack and remove volumes (DESTROYS local data)
	docker compose down -v

shell-%:  ## Shell into a service, e.g. make shell-backend
	docker compose exec $* /bin/sh

# ------------------------------------------------------------------- code
lint:  ## Lint everything
	ruff check backend ai-model alert-system data-pipeline
	cd frontend && npm run lint

format:  ## Auto-format everything
	ruff format backend ai-model alert-system data-pipeline
	ruff check backend ai-model alert-system data-pipeline --fix
	cd frontend && npm run format

test: test-backend test-model test-alerts  ## Run all Python tests

test-backend:
	cd backend && pytest -q

test-model:
	cd ai-model && pytest -q

test-alerts:
	cd alert-system && pytest -q

test-frontend:
	cd frontend && npm run test

# --------------------------------------------------------------- database
migrate:  ## Apply database migrations
	cd backend && alembic upgrade head

seed:  ## Load demo cyclone data
	python scripts/seed_demo_data.py

# ---------------------------------------------------------------- ml jobs
train:  ## Train a model, e.g. make train CONFIG=configs/classifier.yaml
	cd ai-model && python -m src.training.train --config $(or $(CONFIG),configs/config.yaml)

evaluate:  ## Evaluate a checkpoint against IMD best track
	cd ai-model && python -m src.evaluation.evaluate --config $(or $(CONFIG),configs/config.yaml)

ingest:  ## Run one ingestion cycle manually
	cd data-pipeline && python -m src.scheduler --once
