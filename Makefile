# =============================================================================
# Makefile for SystemSTT — macOS desktop speech-to-text application
#
# Usage:
#   make help        Show available targets
#   make install     Install project in editable mode with dev deps
#   make test        Run tests with coverage
#   make lint        Run ruff linter
#   make format      Auto-format code with ruff
#   make typecheck   Run mypy strict type checking
#   make check       Run lint + typecheck + test (CI equivalent)
#   make build       Build macOS .app bundle with PyInstaller
#   make dmg         Build .app + DMG installer
#   make clean       Remove build artifacts
#   make run         Run the application
# =============================================================================

.PHONY: help install dev test lint format typecheck check build dmg clean run \
        pre-commit-install pre-commit-run

SHELL := /bin/bash
PYTHON ?= python3.11
VENV_DIR := .venv
VENV_BIN := $(VENV_DIR)/bin
PIP := $(VENV_BIN)/pip
PYTEST := $(VENV_BIN)/pytest
RUFF := $(VENV_BIN)/ruff
MYPY := $(VENV_BIN)/mypy
PYINSTALLER := $(VENV_BIN)/pyinstaller
PRE_COMMIT := $(VENV_BIN)/pre-commit

SRC_DIRS := src/ tests/
APP_NAME := SystemSTT

# Default target
.DEFAULT_GOAL := help

# ---------------------------------------------------------------------------
# Help
# ---------------------------------------------------------------------------
help: ## Show this help message
	@echo "SystemSTT — Development Commands"
	@echo ""
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | sort | \
		awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[36m%-20s\033[0m %s\n", $$1, $$2}'
	@echo ""

# ---------------------------------------------------------------------------
# Environment Setup
# ---------------------------------------------------------------------------
$(VENV_DIR):
	$(PYTHON) -m venv $(VENV_DIR)

install: $(VENV_DIR) ## Install project with dev + build dependencies
	$(PIP) install --upgrade pip
	$(PIP) install -e ".[dev,build]"
	@echo ""
	@echo "Installation complete. Activate with: source $(VENV_DIR)/bin/activate"

dev: install pre-commit-install ## Full dev setup (install + pre-commit hooks)
	@echo ""
	@echo "Dev environment ready!"

# ---------------------------------------------------------------------------
# Code Quality
# ---------------------------------------------------------------------------
lint: ## Run ruff linter on src/ and tests/
	$(RUFF) check $(SRC_DIRS)

format: ## Auto-format code with ruff
	$(RUFF) format $(SRC_DIRS)
	$(RUFF) check --fix $(SRC_DIRS)

format-check: ## Check formatting without modifying files
	$(RUFF) format --check $(SRC_DIRS)

typecheck: ## Run mypy strict type checking
	$(MYPY) src/systemstt

# ---------------------------------------------------------------------------
# Testing
# ---------------------------------------------------------------------------
test: ## Run tests with coverage report
	$(PYTEST) \
		--cov=systemstt \
		--cov-report=term-missing \
		-v

test-quick: ## Run tests without coverage (faster)
	$(PYTEST) -x -q

test-verbose: ## Run tests with full output
	$(PYTEST) \
		--cov=systemstt \
		--cov-report=term-missing \
		--cov-report=html:htmlcov \
		-v --tb=long

# ---------------------------------------------------------------------------
# Combined Checks (mirrors CI pipeline)
# ---------------------------------------------------------------------------
check: lint format-check typecheck test ## Run all checks (lint + format + typecheck + test)
	@echo ""
	@echo "All checks passed!"

# ---------------------------------------------------------------------------
# Build
# ---------------------------------------------------------------------------
build: ## Build macOS .app bundle with PyInstaller
	./scripts/build_app.sh

dmg: ## Build .app bundle + DMG installer
	./scripts/build_app.sh --dmg

build-clean: ## Clean build, then rebuild
	./scripts/build_app.sh --clean

# ---------------------------------------------------------------------------
# Run
# ---------------------------------------------------------------------------
run: ## Run the application
	$(VENV_BIN)/python -m systemstt

run-debug: ## Run with debug logging
	SYSTEMSTT_LOG_LEVEL=DEBUG $(VENV_BIN)/python -m systemstt

# ---------------------------------------------------------------------------
# Pre-commit Hooks
# ---------------------------------------------------------------------------
pre-commit-install: ## Install pre-commit hooks into .git/hooks
	$(PRE_COMMIT) install

pre-commit-run: ## Run pre-commit hooks on all files
	$(PRE_COMMIT) run --all-files

# ---------------------------------------------------------------------------
# Cleanup
# ---------------------------------------------------------------------------
clean: ## Remove build artifacts, caches, and coverage reports
	rm -rf build/ dist/
	rm -rf *.egg-info src/*.egg-info
	rm -rf .pytest_cache
	rm -rf .mypy_cache
	rm -rf .ruff_cache
	rm -rf htmlcov
	rm -f coverage.xml test-results.xml .coverage
	find . -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true
	@echo "Clean complete"

clean-all: clean ## Remove everything including venv
	rm -rf $(VENV_DIR)
	@echo "Full clean complete (including venv)"
