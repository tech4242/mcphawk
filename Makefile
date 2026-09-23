.PHONY: install install-backend install-frontend build build-frontend dev dev-backend dev-frontend demo test test-unit test-integration test-db test-capture test-network test-install test-cli test-web test-mcp test-e2e coverage lint format clean

# Setup
install: install-backend install-frontend

install-backend:
	pip install -r requirements-dev.txt
	pip install -e .

install-frontend:
	cd frontend && npm install

# Build (the built UI is committed to mcphawk/web/static)
build: build-frontend
	python -m build

build-frontend:
	cd frontend && npm run build

# Development: API on 8484, Vite with hot reload on 5173
dev:
	@make -j 2 dev-backend dev-frontend

dev-backend:
	mcphawk up

dev-frontend:
	cd frontend && npm run dev

# Generate realistic demo traffic into the default database
demo:
	python examples/demo/run_demo.py

# Tests
test:
	python -m pytest -v

test-unit:
	python -m pytest tests/unit -v

test-integration:
	python -m pytest tests/integration -v

test-db:
	python -m pytest tests/integration/db -v

test-capture:
	python -m pytest tests/integration/capture -v

test-network:
	python -m pytest tests/integration/network -v

test-install:
	python -m pytest tests/integration/install -v

test-cli:
	python -m pytest tests/integration/cli -v

test-web:
	python -m pytest tests/integration/web -v

test-mcp:
	python -m pytest tests/integration/mcp -v

test-e2e:
	python -m pytest tests/integration/e2e -v

# Coverage (fails under 85%, see pyproject.toml)
coverage:
	python -m pytest --cov=mcphawk --cov-report=html --cov-report=term --cov-report=xml

# Code quality
lint:
	ruff check .

format:
	ruff check . --fix

clean:
	rm -rf frontend/node_modules build dist *.egg-info htmlcov .coverage coverage.xml
	find . -type d -name __pycache__ -prune -exec rm -rf {} +
	find . -type d -name .pytest_cache -prune -exec rm -rf {} +
