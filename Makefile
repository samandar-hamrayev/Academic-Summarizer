.DEFAULT_GOAL := help
.PHONY: help install run migrate lint format test cov check precommit \
        build up down restart logs shell dmigrate superuser ps clean dev

PYTHON ?= python
COMPOSE ?= docker compose

help: ## Show this help
	@grep -E '^[a-zA-Z_-]+:.*?## ' $(MAKEFILE_LIST) | \
		awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[36m%-11s\033[0m %s\n", $$1, $$2}'

# ── Local development ────────────────────────────────────────────────────────
install: ## Install runtime + dev dependencies and git hooks
	$(PYTHON) -m pip install -r requirements-dev.txt
	pre-commit install

run: ## Run the Django dev server (SQLite unless DATABASE_URL is set)
	$(PYTHON) manage.py migrate
	$(PYTHON) manage.py runserver

migrate: ## Apply migrations locally
	$(PYTHON) manage.py migrate

lint: ## Lint and check formatting with ruff
	ruff check .
	ruff format --check .

format: ## Auto-fix lint issues and format code
	ruff check --fix .
	ruff format .

test: ## Run the test suite
	pytest

cov: ## Run tests with a coverage report
	pytest --cov --cov-report=term-missing

check: lint test ## Lint + tests (what CI runs)

precommit: ## Run all pre-commit hooks on every file
	pre-commit run --all-files

# ── Docker (PostgreSQL + gunicorn + nginx) ───────────────────────────────────
build: ## Build the Docker image
	$(COMPOSE) build

up: ## Start the stack and wait until it is healthy
	$(COMPOSE) up -d --wait

down: ## Stop the stack
	$(COMPOSE) down

restart: ## Restart the web service
	$(COMPOSE) restart web

logs: ## Follow logs
	$(COMPOSE) logs -f --tail=100

shell: ## Django shell inside the web container
	$(COMPOSE) exec web python manage.py shell

dmigrate: ## Run migrations inside the web container
	$(COMPOSE) exec web python manage.py migrate

superuser: ## Create a Django superuser inside the web container
	$(COMPOSE) exec web python manage.py createsuperuser

ps: ## List running containers
	$(COMPOSE) ps

clean: ## Stop the stack and delete its volumes (database + uploads!)
	$(COMPOSE) down -v --remove-orphans

dev: ## Docker dev server with hot reload (SQLite)
	$(COMPOSE) -f docker-compose.dev.yml up --build
