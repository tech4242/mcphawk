.PHONY: install install-frontend build build-frontend dev dev-backend dev-frontend test clean

# Install all dependencies
install: install-backend install-frontend

install-backend:
	pip install -e .
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
	python -m pytest -v

test-watch:
	python -m pytest -v --watch

# Clean
clean:
	rm -rf frontend/node_modules
	rm -rf frontend/dist
	rm -rf mcphawk/web/static/*
	find . -type d -name __pycache__ -exec rm -rf {} +
	find . -type d -name .pytest_cache -exec rm -rf {} +
	find . -type d -name .coverage -exec rm -rf {} +