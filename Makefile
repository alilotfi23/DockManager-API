.PHONY: help up down restart logs test migrate lint format clean install

help: ## Show this help message
	@echo 'Usage: make [target]'
	@echo ''
	@echo 'Available targets:'
	@awk 'BEGIN {FS = ":.*?## "} /^[a-zA-Z_-]+:.*?## / {printf "  %-15s %s\n", $$1, $$2}' $(MAKEFILE_LIST)

install: ## Install dependencies
	pip install -r requirements.txt

up: ## Start the application with docker-compose
	docker-compose up -d

down: ## Stop the application with docker-compose
	docker-compose down

restart: ## Restart the application
	docker-compose restart

logs: ## View application logs
	docker-compose logs -f

dev: ## Run the application in development mode
	uvicorn app.main:app --reload --host 0.0.0.0 --port 8000

test: ## Run tests
	pytest tests/ -v

test-coverage: ## Run tests with coverage
	pytest tests/ --cov=app --cov-report=html --cov-report=term

migrate: ## Run database migrations
	alembic upgrade head

migrate-create: ## Create a new migration (usage: make migrate-create MSG="description")
	alembic revision --autogenerate -m '$(MSG)'

migrate-downgrade: ## Rollback last migration
	alembic downgrade -1

lint: ## Run linting
	ruff check app/
	mypy app/

format: ## Format code with ruff
	ruff format app/

clean: ## Clean up generated files
	find . -type d -name __pycache__ -exec rm -rf {} +
	find . -type f -name "*.pyc" -delete
	find . -type f -name "*.pyo" -delete
	find . -type f -name ".DS_Store" -delete
	rm -rf .pytest_cache
	rm -rf htmlcov
	rm -rf .coverage
	rm -rf .mypy_cache
	rm -rf .ruff_cache

build: ## Build the Docker image
	docker-compose build

rebuild: ## Rebuild the Docker image without cache
	docker-compose build --no-cache

shell: ## Open a shell in the running container
	docker-compose exec docker-api /bin/bash
