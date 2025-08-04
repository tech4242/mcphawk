.PHONY: install install-frontend build build-frontend dev dev-backend dev-frontend test test-unit test-integration test-db test-network test-cli test-web test-mcp test-watch coverage coverage-report lint format format-unsafe clean

# Install all dependencies
install: install-backend install-frontend

install-backend:
	pip3 install -e .
	pip install -r requirements-dev.txt

install-frontend:
	cd frontend && npm install

# Build for production
build: build-frontend

build-frontend:
	cd frontend && npm run build

# Development commands
dev:
	@echo "Starting both backend and frontend..."
	@make -j 2 dev-backend dev-frontend

dev-backend:
	mcphawk web --port 3000

dev-frontend:
	cd frontend && npm run dev

# Testing
test:
	python3 -m pytest -v

test-unit:
	python3 -m pytest tests/unit -v

test-integration:
	python3 -m pytest tests/integration -v

test-db:
	python3 -m pytest tests/integration/db -v

test-network:
	python3 -m pytest tests/integration/network -v

test-cli:
	python3 -m pytest tests/integration/cli -v

test-web:
	python3 -m pytest tests/integration/web -v

test-mcp:
	python3 -m pytest tests/integration/mcp -v

test-watch:
	python3 -m pytest -v --watch

# Coverage
coverage:
	python3 -m pytest -v --cov=mcphawk --cov-report=html --cov-report=term

coverage-report:
	python3 -m pytest -v --cov=mcphawk --cov-report=html --cov-report=term --cov-report=xml
	@echo "Coverage report generated in htmlcov/index.html"

# Linting
lint:
	ruff check .

format:
	ruff check . --fix

format-unsafe:
	ruff check . --fix --unsafe-fixes

# Clean
clean:
	rm -rf frontend/node_modules
	rm -rf frontend/dist
	rm -rf mcphawk/web/static/*
	find . -type d -name __pycache__ -exec rm -rf {} +
	find . -type d -name .pytest_cache -exec rm -rf {} +
	find . -type d -name .coverage -exec rm -rf {} +