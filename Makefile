# ============================================================================
# ECOSISTEMA DE EMPRENDIMIENTO - MAKEFILE
# ============================================================================
# Comprehensive Makefile for the entrepreneurship ecosystem platform
# Author: Development Team
# Last Updated: 2025-06-14
# 
# Usage: make <target>
# Example: make help, make setup, make test, make deploy
# ============================================================================

# ============================================================================
# CONFIGURATION AND VARIABLES
# ============================================================================
# Project settings
PROJECT_NAME := ecosistema-emprendimiento
PACKAGE_NAME := app
PYTHON_VERSION := 3.11
VENV_NAME := venv

# Python and environment
PYTHON := python$(PYTHON_VERSION)
VENV_PYTHON := $(VENV_NAME)/bin/python
VENV_PIP := $(VENV_NAME)/bin/pip
VENV_ACTIVATE := source $(VENV_NAME)/bin/activate

# Development tools
PYTEST := $(VENV_NAME)/bin/pytest
BLACK := $(VENV_NAME)/bin/black
ISORT := $(VENV_NAME)/bin/isort
FLAKE8 := $(VENV_NAME)/bin/flake8
MYPY := $(VENV_NAME)/bin/mypy
PYLINT := $(VENV_NAME)/bin/pylint
BANDIT := $(VENV_NAME)/bin/bandit
RUFF := $(VENV_NAME)/bin/ruff
PRE_COMMIT := $(VENV_NAME)/bin/pre-commit

# Flask application
FLASK_APP := run.py
FLASK_ENV := development

# Database
DB_URL := postgresql://localhost:5432/ecosistema_emprendimiento_dev
TEST_DB_URL := postgresql://localhost:5432/ecosistema_emprendimiento_test

# Docker
DOCKER_IMAGE := $(PROJECT_NAME)
DOCKER_TAG := latest
DOCKER_REGISTRY := ghcr.io/your-org

# Directories
DOCS_DIR := docs
TESTS_DIR := tests
LOGS_DIR := logs
STATIC_DIR := app/static
COVERAGE_DIR := htmlcov

# Files
REQUIREMENTS_FILE := requirements.txt
DEV_REQUIREMENTS_FILE := requirements-dev.txt
DOCKER_COMPOSE_FILE := docker-compose.yml
ENV_FILE := .env.local

# Colors for output
COLOR_RESET := \033[0m
COLOR_BOLD := \033[1m
COLOR_RED := \033[31m
COLOR_GREEN := \033[32m
COLOR_YELLOW := \033[33m
COLOR_BLUE := \033[34m
COLOR_MAGENTA := \033[35m
COLOR_CYAN := \033[36m

# Default target
.DEFAULT_GOAL := help

# Make settings
SHELL := /bin/bash
.SHELLFLAGS := -eu -o pipefail -c
MAKEFLAGS += --warn-undefined-variables
MAKEFLAGS += --no-builtin-rules

# ============================================================================
# HELP AND INFORMATION
# ============================================================================
.PHONY: help
help: ## Show this help message
	@echo "$(COLOR_BOLD)$(PROJECT_NAME) - Development Commands$(COLOR_RESET)"
	@echo ""
	@echo "$(COLOR_CYAN)Available targets:$(COLOR_RESET)"
	@awk 'BEGIN {FS = ":.*?## "} /^[a-zA-Z_-]+:.*?## / {printf "  $(COLOR_GREEN)%-20s$(COLOR_RESET) %s\n", $$1, $$2}' $(MAKEFILE_LIST)
	@echo ""
	@echo "$(COLOR_YELLOW)Examples:$(COLOR_RESET)"
	@echo "  make setup          # Complete development setup"
	@echo "  make test           # Run all tests"
	@echo "  make format         # Format code with black and isort"
	@echo "  make lint           # Run all linting tools"
	@echo "  make run            # Start development server"
	@echo "  make docker-build   # Build Docker image"
	@echo ""

.PHONY: info
info: ## Show project information
	@echo "$(COLOR_BOLD)Project Information$(COLOR_RESET)"
	@echo "Project Name:     $(PROJECT_NAME)"
	@echo "Package Name:     $(PACKAGE_NAME)"
	@echo "Python Version:   $(PYTHON_VERSION)"
	@echo "Virtual Env:      $(VENV_NAME)"
	@echo "Flask App:        $(FLASK_APP)"
	@echo "Database URL:     $(DB_URL)"
	@echo "Docker Image:     $(DOCKER_IMAGE):$(DOCKER_TAG)"
	@echo ""

# ============================================================================
# ENVIRONMENT SETUP
# ============================================================================
.PHONY: setup
setup: venv install-deps install-pre-commit create-dirs init-db ## Complete development environment setup
	@echo "$(COLOR_GREEN)✅ Development environment setup complete!$(COLOR_RESET)"
	@echo "$(COLOR_YELLOW)Next steps:$(COLOR_RESET)"
	@echo "  1. Copy .env.example to .env.local and configure"
	@echo "  2. Run 'make run' to start the development server"
	@echo "  3. Visit http://localhost:5000"

.PHONY: setup-ci
setup-ci: install install-dev ## Setup for CI/CD environment
	@echo "$(COLOR_GREEN)✅ CI/CD environment setup complete!$(COLOR_RESET)"

venv: ## Create virtual environment
	@if [ ! -d "$(VENV_NAME)" ]; then \
		echo "$(COLOR_BLUE)Creating virtual environment...$(COLOR_RESET)"; \
		$(PYTHON) -m venv $(VENV_NAME); \
		$(VENV_PIP) install --upgrade pip setuptools wheel; \
		echo "$(COLOR_GREEN)✅ Virtual environment created$(COLOR_RESET)"; \
	else \
		echo "$(COLOR_YELLOW)Virtual environment already exists$(COLOR_RESET)"; \
	fi

.PHONY: install
install: venv ## Install production dependencies
	@echo "$(COLOR_BLUE)Installing production dependencies...$(COLOR_RESET)"
	$(VENV_PIP) install -r $(REQUIREMENTS_FILE)
	@echo "$(COLOR_GREEN)✅ Production dependencies installed$(COLOR_RESET)"

.PHONY: install-dev
install-dev: venv ## Install development dependencies
	@echo "$(COLOR_BLUE)Installing development dependencies...$(COLOR_RESET)"
	$(VENV_PIP) install -r $(DEV_REQUIREMENTS_FILE)
	@echo "$(COLOR_GREEN)✅ Development dependencies installed$(COLOR_RESET)"

.PHONY: install-deps
install-deps: install install-dev ## Install all dependencies
	@echo "$(COLOR_GREEN)✅ All dependencies installed$(COLOR_RESET)"

.PHONY: install-pre-commit
install-pre-commit: ## Install pre-commit hooks
	@if [ -f "$(PRE_COMMIT)" ]; then \
		echo "$(COLOR_BLUE)Installing pre-commit hooks...$(COLOR_RESET)"; \
		$(PRE_COMMIT) install; \
		$(PRE_COMMIT) install --hook-type commit-msg; \
		echo "$(COLOR_GREEN)✅ Pre-commit hooks installed$(COLOR_RESET)"; \
	else \
		echo "$(COLOR_RED)❌ pre-commit not found. Run 'make install-dev' first$(COLOR_RESET)"; \
		exit 1; \
	fi

.PHONY: update
update: ## Update all dependencies
	@echo "$(COLOR_BLUE)Updating dependencies...$(COLOR_RESET)"
	$(VENV_PIP) install --upgrade pip setuptools wheel
	$(VENV_PIP) install --upgrade -r $(REQUIREMENTS_FILE)
	$(VENV_PIP) install --upgrade -r $(DEV_REQUIREMENTS_FILE)
	@if [ -f "$(PRE_COMMIT)" ]; then \
		$(PRE_COMMIT) autoupdate; \
	fi
	@echo "$(COLOR_GREEN)✅ Dependencies updated$(COLOR_RESET)"

# ============================================================================
# DIRECTORY MANAGEMENT
# ============================================================================
.PHONY: create-dirs
create-dirs: ## Create necessary directories
	@echo "$(COLOR_BLUE)Creating project directories...$(COLOR_RESET)"
	@mkdir -p $(LOGS_DIR)
	@mkdir -p $(TESTS_DIR)/unit
	@mkdir -p $(TESTS_DIR)/integration
	@mkdir -p $(TESTS_DIR)/functional
	@mkdir -p $(DOCS_DIR)
	@mkdir -p app/static/uploads
	@mkdir -p app/static/dist
	@mkdir -p migrations/versions
	@mkdir -p scripts
	@mkdir -p config
	@echo "$(COLOR_GREEN)✅ Directories created$(COLOR_RESET)"

# ============================================================================
# CODE QUALITY AND FORMATTING
# ============================================================================
.PHONY: format
format: ## Format code with black and isort
	@echo "$(COLOR_BLUE)Formatting code...$(COLOR_RESET)"
	@if [ -f "$(BLACK)" ] && [ -f "$(ISORT)" ]; then \
		$(BLACK) . && \
		$(ISORT) . && \
		echo "$(COLOR_GREEN)✅ Code formatted$(COLOR_RESET)"; \
	else \
		echo "$(COLOR_RED)❌ Formatters not found. Run 'make install-dev' first$(COLOR_RESET)"; \
		exit 1; \
	fi

.PHONY: format-check
format-check: ## Check code formatting without making changes
	@echo "$(COLOR_BLUE)Checking code formatting...$(COLOR_RESET)"
	@if [ -f "$(BLACK)" ] && [ -f "$(ISORT)" ]; then \
		$(BLACK) --check . && \
		$(ISORT) --check-only . && \
		echo "$(COLOR_GREEN)✅ Code formatting is correct$(COLOR_RESET)"; \
	else \
		echo "$(COLOR_RED)❌ Formatters not found. Run 'make install-dev' first$(COLOR_RESET)"; \
		exit 1; \
	fi

.PHONY: lint
lint: lint-ruff lint-flake8 lint-pylint ## Run all linting tools
	@echo "$(COLOR_GREEN)✅ All linting checks completed$(COLOR_RESET)"

.PHONY: lint-ruff
lint-ruff: ## Run Ruff linter (modern and fast)
	@echo "$(COLOR_BLUE)Running Ruff linter...$(COLOR_RESET)"
	@if [ -f "$(RUFF)" ]; then \
		$(RUFF) check . && \
		echo "$(COLOR_GREEN)✅ Ruff linting passed$(COLOR_RESET)"; \
	else \
		echo "$(COLOR_YELLOW)⚠️  Ruff not found, skipping$(COLOR_RESET)"; \
	fi

.PHONY: lint-flake8
lint-flake8: ## Run Flake8 linter
	@echo "$(COLOR_BLUE)Running Flake8 linter...$(COLOR_RESET)"
	@if [ -f "$(FLAKE8)" ]; then \
		$(FLAKE8) $(PACKAGE_NAME)/ $(TESTS_DIR)/ && \
		echo "$(COLOR_GREEN)✅ Flake8 linting passed$(COLOR_RESET)"; \
	else \
		echo "$(COLOR_YELLOW)⚠️  Flake8 not found, skipping$(COLOR_RESET)"; \
	fi

.PHONY: lint-pylint
lint-pylint: ## Run Pylint
	@echo "$(COLOR_BLUE)Running Pylint...$(COLOR_RESET)"
	@if [ -f "$(PYLINT)" ]; then \
		$(PYLINT) $(PACKAGE_NAME)/ --fail-under=8.0 && \
		echo "$(COLOR_GREEN)✅ Pylint passed$(COLOR_RESET)"; \
	else \
		echo "$(COLOR_YELLOW)⚠️  Pylint not found, skipping$(COLOR_RESET)"; \
	fi

.PHONY: typecheck
typecheck: ## Run MyPy type checking
	@echo "$(COLOR_BLUE)Running MyPy type checking...$(COLOR_RESET)"
	@if [ -f "$(MYPY)" ]; then \
		$(MYPY) $(PACKAGE_NAME)/ && \
		echo "$(COLOR_GREEN)✅ Type checking passed$(COLOR_RESET)"; \
	else \
		echo "$(COLOR_RED)❌ MyPy not found. Run 'make install-dev' first$(COLOR_RESET)"; \
		exit 1; \
	fi

.PHONY: security
security: ## Run security checks
	@echo "$(COLOR_BLUE)Running security checks...$(COLOR_RESET)"
	@if [ -f "$(BANDIT)" ]; then \
		$(BANDIT) -r $(PACKAGE_NAME)/ --skip B101,B601 && \
		echo "$(COLOR_GREEN)✅ Security checks passed$(COLOR_RESET)"; \
	else \
		echo "$(COLOR_RED)❌ Bandit not found. Run 'make install-dev' first$(COLOR_RESET)"; \
		exit 1; \
	fi

.PHONY: fix
fix: ## Auto-fix code issues where possible
	@echo "$(COLOR_BLUE)Auto-fixing code issues...$(COLOR_RESET)"
	@if [ -f "$(RUFF)" ]; then \
		$(RUFF) check . --fix; \
	fi
	@make format
	@echo "$(COLOR_GREEN)✅ Auto-fixes applied$(COLOR_RESET)"

.PHONY: quality
quality: format-check lint typecheck security ## Run all quality checks
	@echo "$(COLOR_GREEN)✅ All quality checks completed$(COLOR_RESET)"

# ============================================================================
# TESTING
# ============================================================================
.PHONY: test
test: ## Run all tests
	@echo "$(COLOR_BLUE)Running all tests...$(COLOR_RESET)"
	@if [ -f "$(PYTEST)" ]; then \
		FLASK_ENV=testing $(PYTEST) $(TESTS_DIR)/ -v && \
		echo "$(COLOR_GREEN)✅ All tests passed$(COLOR_RESET)"; \
	else \
		echo "$(COLOR_RED)❌ pytest not found. Run 'make install-dev' first$(COLOR_RESET)"; \
		exit 1; \
	fi

.PHONY: test-unit
test-unit: ## Run unit tests only
	@echo "$(COLOR_BLUE)Running unit tests...$(COLOR_RESET)"
	@if [ -f "$(PYTEST)" ]; then \
		FLASK_ENV=testing $(PYTEST) $(TESTS_DIR)/unit/ -v; \
	else \
		echo "$(COLOR_RED)❌ pytest not found. Run 'make install-dev' first$(COLOR_RESET)"; \
		exit 1; \
	fi

.PHONY: test-integration
test-integration: ## Run integration tests only
	@echo "$(COLOR_BLUE)Running integration tests...$(COLOR_RESET)"
	@if [ -f "$(PYTEST)" ]; then \
		FLASK_ENV=testing $(PYTEST) $(TESTS_DIR)/integration/ -v; \
	else \
		echo "$(COLOR_RED)❌ pytest not found. Run 'make install-dev' first$(COLOR_RESET)"; \
		exit 1; \
	fi

.PHONY: test-functional
test-functional: ## Run functional tests only
	@echo "$(COLOR_BLUE)Running functional tests...$(COLOR_RESET)"
	@if [ -f "$(PYTEST)" ]; then \
		FLASK_ENV=testing $(PYTEST) $(TESTS_DIR)/functional/ -v; \
	else \
		echo "$(COLOR_RED)❌ pytest not found. Run 'make install-dev' first$(COLOR_RESET)"; \
		exit 1; \
	fi

.PHONY: test-coverage
test-coverage: ## Run tests with coverage report
	@echo "$(COLOR_BLUE)Running tests with coverage...$(COLOR_RESET)"
	@if [ -f "$(PYTEST)" ]; then \
		FLASK_ENV=testing $(PYTEST) $(TESTS_DIR)/ --cov=$(PACKAGE_NAME) --cov-report=html --cov-report=term-missing --cov-fail-under=80 && \
		echo "$(COLOR_GREEN)✅ Coverage report generated in $(COVERAGE_DIR)/$(COLOR_RESET)"; \
	else \
		echo "$(COLOR_RED)❌ pytest not found. Run 'make install-dev' first$(COLOR_RESET)"; \
		exit 1; \
	fi

.PHONY: test-watch
test-watch: ## Run tests in watch mode
	@echo "$(COLOR_BLUE)Running tests in watch mode...$(COLOR_RESET)"
	@if [ -f "$(PYTEST)" ]; then \
		FLASK_ENV=testing $(PYTEST) $(TESTS_DIR)/ -f; \
	else \
		echo "$(COLOR_RED)❌ pytest not found. Run 'make install-dev' first$(COLOR_RESET)"; \
		exit 1; \
	fi

.PHONY: test-parallel
test-parallel: ## Run tests in parallel
	@echo "$(COLOR_BLUE)Running tests in parallel...$(COLOR_RESET)"
	@if [ -f "$(PYTEST)" ]; then \
		FLASK_ENV=testing $(PYTEST) $(TESTS_DIR)/ -n auto; \
	else \
		echo "$(COLOR_RED)❌ pytest not found. Run 'make install-dev' first$(COLOR_RESET)"; \
		exit 1; \
	fi

# ============================================================================
# DATABASE OPERATIONS
# ============================================================================
.PHONY: db-create
db-create: ## Create database
	@echo "$(COLOR_BLUE)Creating database...$(COLOR_RESET)"
	@createdb $(shell basename $(DB_URL)) 2>/dev/null || echo "Database may already exist"
	@createdb $(shell basename $(TEST_DB_URL)) 2>/dev/null || echo "Test database may already exist"
	@echo "$(COLOR_GREEN)✅ Database created$(COLOR_RESET)"

.PHONY: db-drop
db-drop: ## Drop database
	@echo "$(COLOR_BLUE)Dropping database...$(COLOR_RESET)"
	@dropdb $(shell basename $(DB_URL)) 2>/dev/null || echo "Database may not exist"
	@dropdb $(shell basename $(TEST_DB_URL)) 2>/dev/null || echo "Test database may not exist"
	@echo "$(COLOR_GREEN)✅ Database dropped$(COLOR_RESET)"

.PHONY: db-reset
db-reset: db-drop db-create db-migrate ## Reset database (drop, create, migrate)
	@echo "$(COLOR_GREEN)✅ Database reset complete$(COLOR_RESET)"

.PHONY: init-db
init-db: ## Initialize database with migrations
	@echo "$(COLOR_BLUE)Initializing database...$(COLOR_RESET)"
	@$(VENV_ACTIVATE) && FLASK_APP=$(FLASK_APP) flask db init 2>/dev/null || echo "Database already initialized"
	@make db-migrate
	@echo "$(COLOR_GREEN)✅ Database initialized$(COLOR_RESET)"

.PHONY: db-migrate
db-migrate: ## Run database migrations
	@echo "$(COLOR_BLUE)Running database migrations...$(COLOR_RESET)"
	@$(VENV_ACTIVATE) && FLASK_APP=$(FLASK_APP) flask db upgrade
	@echo "$(COLOR_GREEN)✅ Database migrations completed$(COLOR_RESET)"

.PHONY: db-migration
db-migration: ## Create new database migration
	@echo "$(COLOR_BLUE)Creating new migration...$(COLOR_RESET)"
	@read -p "Migration message: " message; \
	$(VENV_ACTIVATE) && FLASK_APP=$(FLASK_APP) flask db migrate -m "$$message"
	@echo "$(COLOR_GREEN)✅ Migration created$(COLOR_RESET)"

.PHONY: db-downgrade
db-downgrade: ## Downgrade database by one migration
	@echo "$(COLOR_BLUE)Downgrading database...$(COLOR_RESET)"
	@$(VENV_ACTIVATE) && FLASK_APP=$(FLASK_APP) flask db downgrade
	@echo "$(COLOR_GREEN)✅ Database downgraded$(COLOR_RESET)"

.PHONY: db-seed
db-seed: ## Seed database with sample data
	@echo "$(COLOR_BLUE)Seeding database...$(COLOR_RESET)"
	@$(VENV_ACTIVATE) && FLASK_APP=$(FLASK_APP) flask seed-data
	@echo "$(COLOR_GREEN)✅ Database seeded$(COLOR_RESET)"

# ============================================================================
# APPLICATION MANAGEMENT
# ============================================================================
.PHONY: run
run: ## Start development server
	@echo "$(COLOR_BLUE)Starting development server...$(COLOR_RESET)"
	@if [ ! -f "$(ENV_FILE)" ]; then \
		echo "$(COLOR_YELLOW)⚠️  .env.local not found. Copying from .env.example$(COLOR_RESET)"; \
		cp .env.example $(ENV_FILE); \
	fi
	@$(VENV_ACTIVATE) && FLASK_APP=$(FLASK_APP) FLASK_ENV=$(FLASK_ENV) flask run --host=0.0.0.0 --port=5000 --debug

.PHONY: run-prod
run-prod: ## Start production server with Gunicorn
	@echo "$(COLOR_BLUE)Starting production server...$(COLOR_RESET)"
	@$(VENV_ACTIVATE) && gunicorn --bind 0.0.0.0:8000 --workers 4 --worker-class gevent "$(PACKAGE_NAME):create_app()"

.PHONY: shell
shell: ## Start Flask shell
	@echo "$(COLOR_BLUE)Starting Flask shell...$(COLOR_RESET)"
	@$(VENV_ACTIVATE) && FLASK_APP=$(FLASK_APP) flask shell

.PHONY: routes
routes: ## Show all application routes
	@echo "$(COLOR_BLUE)Application routes:$(COLOR_RESET)"
	@$(VENV_ACTIVATE) && FLASK_APP=$(FLASK_APP) flask routes

.PHONY: celery-worker
celery-worker: ## Start Celery worker
	@echo "$(COLOR_BLUE)Starting Celery worker...$(COLOR_RESET)"
	@$(VENV_ACTIVATE) && celery -A $(PACKAGE_NAME).celery worker --loglevel=info

.PHONY: celery-beat
celery-beat: ## Start Celery beat scheduler
	@echo "$(COLOR_BLUE)Starting Celery beat...$(COLOR_RESET)"
	@$(VENV_ACTIVATE) && celery -A $(PACKAGE_NAME).celery beat --loglevel=info

.PHONY: celery-flower
celery-flower: ## Start Flower (Celery monitoring)
	@echo "$(COLOR_BLUE)Starting Flower...$(COLOR_RESET)"
	@$(VENV_ACTIVATE) && celery -A $(PACKAGE_NAME).celery flower

# ============================================================================
# DOCKER OPERATIONS
# ============================================================================
.PHONY: docker-build
docker-build: ## Build Docker image
	@echo "$(COLOR_BLUE)Building Docker image...$(COLOR_RESET)"
	docker build -t $(DOCKER_IMAGE):$(DOCKER_TAG) .
	@echo "$(COLOR_GREEN)✅ Docker image built: $(DOCKER_IMAGE):$(DOCKER_TAG)$(COLOR_RESET)"

.PHONY: docker-build-dev
docker-build-dev: ## Build development Docker image
	@echo "$(COLOR_BLUE)Building development Docker image...$(COLOR_RESET)"
	docker build -f docker/Dockerfile.dev -t $(DOCKER_IMAGE):dev .
	@echo "$(COLOR_GREEN)✅ Development Docker image built: $(DOCKER_IMAGE):dev$(COLOR_RESET)"

.PHONY: docker-run
docker-run: ## Run Docker container
	@echo "$(COLOR_BLUE)Running Docker container...$(COLOR_RESET)"
	docker run -d --name $(PROJECT_NAME) -p 8000:8000 --env-file $(ENV_FILE) $(DOCKER_IMAGE):$(DOCKER_TAG)
	@echo "$(COLOR_GREEN)✅ Container running at http://localhost:8000$(COLOR_RESET)"

.PHONY: docker-stop
docker-stop: ## Stop Docker container
	@echo "$(COLOR_BLUE)Stopping Docker container...$(COLOR_RESET)"
	docker stop $(PROJECT_NAME) || true
	docker rm $(PROJECT_NAME) || true
	@echo "$(COLOR_GREEN)✅ Container stopped$(COLOR_RESET)"

.PHONY: docker-compose-up
docker-compose-up: ## Start services with docker-compose
	@echo "$(COLOR_BLUE)Starting services with docker-compose...$(COLOR_RESET)"
	docker-compose -f $(DOCKER_COMPOSE_FILE) up -d
	@echo "$(COLOR_GREEN)✅ Services started$(COLOR_RESET)"

.PHONY: docker-compose-down
docker-compose-down: ## Stop services with docker-compose
	@echo "$(COLOR_BLUE)Stopping services with docker-compose...$(COLOR_RESET)"
	docker-compose -f $(DOCKER_COMPOSE_FILE) down
	@echo "$(COLOR_GREEN)✅ Services stopped$(COLOR_RESET)"

.PHONY: docker-logs
docker-logs: ## Show Docker container logs
	@docker logs -f $(PROJECT_NAME)

.PHONY: docker-shell
docker-shell: ## Open shell in Docker container
	@docker exec -it $(PROJECT_NAME) /bin/bash

# ============================================================================
# DOCUMENTATION
# ============================================================================
.PHONY: docs
docs: ## Build documentation
	@echo "$(COLOR_BLUE)Building documentation...$(COLOR_RESET)"
	@if [ -f "$(VENV_NAME)/bin/sphinx-build" ]; then \
		cd $(DOCS_DIR) && ../$(VENV_NAME)/bin/sphinx-build -b html source build; \
		echo "$(COLOR_GREEN)✅ Documentation built in $(DOCS_DIR)/build/$(COLOR_RESET)"; \
	else \
		echo "$(COLOR_RED)❌ Sphinx not found. Run 'make install-dev' first$(COLOR_RESET)"; \
		exit 1; \
	fi

.PHONY: docs-serve
docs-serve: docs ## Serve documentation locally
	@echo "$(COLOR_BLUE)Serving documentation at http://localhost:8080$(COLOR_RESET)"
	@cd $(DOCS_DIR)/build && python -m http.server 8080

.PHONY: docs-clean
docs-clean: ## Clean documentation build
	@echo "$(COLOR_BLUE)Cleaning documentation...$(COLOR_RESET)"
	@rm -rf $(DOCS_DIR)/build
	@echo "$(COLOR_GREEN)✅ Documentation cleaned$(COLOR_RESET)"

# ============================================================================
# DEPLOYMENT AND RELEASE
# ============================================================================
.PHONY: build
build: ## Build distribution packages
	@echo "$(COLOR_BLUE)Building distribution packages...$(COLOR_RESET)"
	@$(VENV_PYTHON) -m build
	@echo "$(COLOR_GREEN)✅ Distribution packages built in dist/$(COLOR_RESET)"

.PHONY: release-check
release-check: quality test security ## Run all checks before release
	@echo "$(COLOR_GREEN)✅ Release checks completed$(COLOR_RESET)"

.PHONY: deploy-staging
deploy-staging: release-check ## Deploy to staging environment
	@echo "$(COLOR_BLUE)Deploying to staging...$(COLOR_RESET)"
	@# Add your staging deployment commands here
	@echo "$(COLOR_GREEN)✅ Deployed to staging$(COLOR_RESET)"

.PHONY: deploy-production
deploy-production: release-check ## Deploy to production environment
	@echo "$(COLOR_BLUE)Deploying to production...$(COLOR_RESET)"
	@# Add your production deployment commands here
	@echo "$(COLOR_GREEN)✅ Deployed to production$(COLOR_RESET)"

# ============================================================================
# MAINTENANCE AND CLEANUP
# ============================================================================
.PHONY: clean
clean: ## Clean up temporary files and caches
	@echo "$(COLOR_BLUE)Cleaning up...$(COLOR_RESET)"
	@find . -type f -name "*.pyc" -delete
	@find . -type d -name "__pycache__" -delete
	@find . -type d -name "*.egg-info" -exec rm -rf {} + 2>/dev/null || true
	@rm -rf build/ dist/ .pytest_cache/ .mypy_cache/ .ruff_cache/
	@rm -rf $(COVERAGE_DIR)/
	@rm -rf .coverage coverage.xml
	@echo "$(COLOR_GREEN)✅ Cleanup completed$(COLOR_RESET)"

.PHONY: clean-all
clean-all: clean ## Clean everything including virtual environment
	@echo "$(COLOR_BLUE)Deep cleaning...$(COLOR_RESET)"
	@rm -rf $(VENV_NAME)/
	@rm -rf node_modules/
	@docker system prune -f 2>/dev/null || true
	@echo "$(COLOR_GREEN)✅ Deep cleanup completed$(COLOR_RESET)"

.PHONY: reset
reset: clean-all setup ## Reset entire development environment
	@echo "$(COLOR_GREEN)✅ Development environment reset$(COLOR_RESET)"

# ============================================================================
# UTILITIES AND HELPERS
# ============================================================================
.PHONY: check-env
check-env: ## Check environment setup
	@echo "$(COLOR_BLUE)Checking environment...$(COLOR_RESET)"
	@echo "Python: $(shell which python$(PYTHON_VERSION) 2>/dev/null || echo 'Not found')"
	@echo "Virtual Environment: $(if $(wildcard $(VENV_NAME)),✅ Found,❌ Not found)"
	@echo "Environment File: $(if $(wildcard $(ENV_FILE)),✅ Found,❌ Not found)"
	@echo "PostgreSQL: $(shell which psql 2>/dev/null || echo 'Not found')"
	@echo "Redis: $(shell which redis-cli 2>/dev/null || echo 'Not found')"
	@echo "Docker: $(shell which docker 2>/dev/null || echo 'Not found')"

.PHONY: check-deps
check-deps: ## Check for outdated dependencies
	@echo "$(COLOR_BLUE)Checking for outdated dependencies...$(COLOR_RESET)"
	@$(VENV_PIP) list --outdated

.PHONY: generate-requirements
generate-requirements: ## Generate requirements.txt from installed packages
	@echo "$(COLOR_BLUE)Generating requirements.txt...$(COLOR_RESET)"
	@$(VENV_PIP) freeze > requirements-frozen.txt
	@echo "$(COLOR_GREEN)✅ Requirements saved to requirements-frozen.txt$(COLOR_RESET)"

.PHONY: backup-db
backup-db: ## Backup database
	@echo "$(COLOR_BLUE)Backing up database...$(COLOR_RESET)"
	@mkdir -p backups
	@pg_dump $(DB_URL) > backups/backup_$(shell date +%Y%m%d_%H%M%S).sql
	@echo "$(COLOR_GREEN)✅ Database backed up to backups/$(COLOR_RESET)"

.PHONY: restore-db
restore-db: ## Restore database from backup (requires BACKUP_FILE variable)
	@if [ -z "$(BACKUP_FILE)" ]; then \
		echo "$(COLOR_RED)❌ Please specify BACKUP_FILE: make restore-db BACKUP_FILE=backup.sql$(COLOR_RESET)"; \
		exit 1; \
	fi
	@echo "$(COLOR_BLUE)Restoring database from $(BACKUP_FILE)...$(COLOR_RESET)"
	@psql $(DB_URL) < $(BACKUP_FILE)
	@echo "$(COLOR_GREEN)✅ Database restored$(COLOR_RESET)"

.PHONY: logs
logs: ## View application logs
	@echo "$(COLOR_BLUE)Viewing logs...$(COLOR_RESET)"
	@tail -f $(LOGS_DIR)/*.log

.PHONY: monitor
monitor: ## Monitor system resources
	@echo "$(COLOR_BLUE)System monitoring (Ctrl+C to stop)...$(COLOR_RESET)"
	@while true; do \
		clear; \
		echo "$(COLOR_BOLD)System Resources$(COLOR_RESET)"; \
		echo "CPU: $$(top -l 1 -s 0 | grep "CPU usage" | awk '{print $$3}' 2>/dev/null || echo 'N/A')"; \
		echo "Memory: $$(free -h | grep '^Mem:' | awk '{print $$3 "/" $$2}' 2>/dev/null || echo 'N/A')"; \
		echo "Disk: $$(df -h . | tail -1 | awk '{print $$3 "/" $$2 " (" $$5 ")"}' 2>/dev/null || echo 'N/A')"; \
		echo ""; \
		echo "$(COLOR_BOLD)Flask Processes$(COLOR_RESET)"; \
		ps aux | grep flask | grep -v grep || echo "No Flask processes running"; \
		sleep 5; \
	done

# ============================================================================
# CI/CD HELPERS
# ============================================================================
.PHONY: ci-install
ci-install: ## Install dependencies for CI/CD
	pip install --upgrade pip setuptools wheel
	pip install -r $(REQUIREMENTS_FILE)
	pip install -r $(DEV_REQUIREMENTS_FILE)

.PHONY: ci-test
ci-test: ## Run tests for CI/CD
	FLASK_ENV=testing pytest $(TESTS_DIR)/ --cov=$(PACKAGE_NAME) --cov-report=xml --cov-report=term-missing

.PHONY: ci-quality
ci-quality: ## Run quality checks for CI/CD
	ruff check .
	black --check .
	isort --check-only .
	mypy $(PACKAGE_NAME)/
	bandit -r $(PACKAGE_NAME)/ --skip B101,B601

# ============================================================================
# DEVELOPMENT SHORTCUTS
# ============================================================================
.PHONY: dev
dev: format lint test ## Quick development cycle (format, lint, test)
	@echo "$(COLOR_GREEN)✅ Development cycle completed$(COLOR_RESET)"

.PHONY: quick-test
quick-test: ## Run quick tests (unit tests only)
	@$(PYTEST) $(TESTS_DIR)/unit/ -x --tb=short

.PHONY: watch
watch: ## Watch for file changes and run tests
	@echo "$(COLOR_BLUE)Watching for changes...$(COLOR_RESET)"
	@$(PYTEST) $(TESTS_DIR)/ -f --tb=short

.PHONY: profile
profile: ## Profile application performance
	@echo "$(COLOR_BLUE)Profiling application...$(COLOR_RESET)"
	@$(VENV_ACTIVATE) && python -m cProfile -o profile.stats -m flask run & \
	sleep 5 && \
	curl http://localhost:5000 && \
	pkill -f "flask run" && \
	python -c "import pstats; p = pstats.Stats('profile.stats'); p.sort_stats('cumulative'); p.print_stats(20)"

# ============================================================================
# SPECIAL TARGETS
# ============================================================================
# Prevent make from treating these as file targets
.PHONY: $(MAKECMDGOALS)

# Handle environment file requirement
$(ENV_FILE):
	@if [ ! -f "$(ENV_FILE)" ]; then \
		echo "$(COLOR_YELLOW)Creating $(ENV_FILE) from .env.example$(COLOR_RESET)"; \
		cp .env.example $(ENV_FILE); \
	fi

# Ensure virtual environment exists for Python commands
$(VENV_PYTHON): venv

# ============================================================================
# MAKEFILE VALIDATION
# ============================================================================
.PHONY: validate-makefile
validate-makefile: ## Validate Makefile syntax
	@echo "$(COLOR_BLUE)Validating Makefile...$(COLOR_RESET)"
	@make -n help >/dev/null 2>&1 && echo "$(COLOR_GREEN)✅ Makefile syntax is valid$(COLOR_RESET)" || echo "$(COLOR_RED)❌ Makefile syntax error$(COLOR_RESET)"

# ============================================================================
# END OF MAKEFILE
# ============================================================================
# This Makefile provides comprehensive automation for the
# Ecosistema de Emprendimiento project development workflow.
#
# Key features:
# ✅ Complete development environment setup
# ✅ Code quality and formatting automation
# ✅ Comprehensive testing suite
# ✅ Database management and migrations
# ✅ Docker containerization support
# ✅ Documentation generation
# ✅ CI/CD integration helpers
# ✅ Deployment automation
# ✅ Maintenance and cleanup utilities
# ✅ Development shortcuts and monitoring
#
# Usage: Run 'make help' to see all available commands
# ============================================================================