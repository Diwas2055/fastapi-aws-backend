# Makefile for FastAPI AWS Backend

.PHONY: help install dev test lint format migrate-up migrate-down docker-up docker-down docker-logs clean

# Default target
help:
	@echo "FastAPI AWS Backend - Available commands:"
	@echo ""
	@echo "Development:"
	@echo "  make install       - Install dependencies"
	@echo "  make dev           - Run development server"
	@echo "  make worker        - Run Celery worker"
	@echo "  make beat          - Run Celery beat"
	@echo ""
	@echo "Testing:"
	@echo "  make test          - Run tests"
	@echo "  make test-cov      - Run tests with coverage"
	@echo "  make test-watch    - Run tests in watch mode"
	@echo ""
	@echo "Code Quality:"
	@echo "  make lint          - Run linters (ruff, mypy)"
	@echo "  make format        - Format code (ruff)"
	@echo "  make type-check    - Run type checking (mypy)"
	@echo ""
	@echo "Database:"
	@echo "  make migrate-up    - Apply migrations"
	@echo "  make migrate-down  - Rollback last migration"
	@echo "  make migrate-new   - Create new migration"
	@echo "  make db-reset      - Reset database"
	@echo ""
	@echo "Docker:"
	@echo "  make docker-up     - Start all services"
	@echo "  make docker-down   - Stop all services"
	@echo "  make docker-logs   - View service logs"
	@echo "  make docker-build  - Build Docker image"
	@echo "  make docker-shell  - Shell into app container"
	@echo ""
	@echo "Utilities:"
	@echo "  make clean         - Clean cache files"
	@echo "  make shell         - Open Python shell"

# Development
install:
	pip install -r requirements.txt
	pre-commit install

dev:
	uvicorn app.main:app --reload --host 0.0.0.0 --port 8000

worker:
	celery -A app.core.celery_app worker --loglevel=info

beat:
	celery -A app.core.celery_app beat --loglevel=info

shell:
	python -c "from app.main import app; print('App loaded')"

# Testing
test:
	pytest -v

test-cov:
	pytest --cov=app --cov-report=html --cov-report=term

test-watch:
	pytest-watch -v

test-unit:
	pytest -m unit -v

test-integration:
	pytest -m integration -v

# Code Quality
lint:
	ruff check .
	mypy app

format:
	ruff check --fix .
	ruff format .

type-check:
	mypy app

# Database
migrate-up:
	alembic upgrade head

migrate-down:
	alembic downgrade -1

migrate-new:
	@read -p "Migration message: " msg; \
	alembic revision --autogenerate -m "$$msg"

migrate-history:
	alembic history

db-reset:
	alembic downgrade base
	alembic upgrade head

# Docker
docker-up:
	docker-compose up -d

docker-down:
	docker-compose down

docker-down-v:
	docker-compose down -v

docker-logs:
	docker-compose logs -f

docker-logs-app:
	docker-compose logs -f app

docker-build:
	docker-compose build

docker-rebuild:
	docker-compose build --no-cache

docker-shell:
	docker-compose exec app bash

docker-db-shell:
	docker-compose exec postgres psql -U postgres -d fastapi_app

docker-redis-shell:
	docker-compose exec redis redis-cli

# Clean
clean:
	find . -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true
	find . -type f -name "*.pyc" -delete
	find . -type f -name "*.pyo" -delete
	find . -type f -name "*.pyd" -delete
	find . -type d -name ".pytest_cache" -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name ".mypy_cache" -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name ".ruff_cache" -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name "htmlcov" -exec rm -rf {} + 2>/dev/null || true
	rm -rf .coverage coverage.xml

# AWS (LocalStack)
aws-create-resources:
	@echo "Creating AWS resources in LocalStack..."
	aws --endpoint-url=http://localhost:4566 s3 mb s3://fastapi-uploads --region us-east-1
	aws --endpoint-url=http://localhost:4566 dynamodb create-table \
		--table-name fastapi-items \
		--attribute-definitions AttributeName=pk,AttributeType=S AttributeName=sk,AttributeType=S \
		--key-schema AttributeName=pk,KeyType=HASH AttributeName=sk,KeyType=RANGE \
		--billing-mode PAY_PER_REQUEST \
		--region us-east-1
	aws --endpoint-url=http://localhost:4566 sqs create-queue --queue-name fastapi-queue --region us-east-1
	aws --endpoint-url=http://localhost:4566 sns create-topic --name fastapi-notifications --region us-east-1

aws-list-resources:
	@echo "S3 Buckets:"
	aws --endpoint-url=http://localhost:4566 s3 ls
	@echo ""
	@echo "DynamoDB Tables:"
	aws --endpoint-url=http://localhost:4566 dynamodb list-tables --region us-east-1
	@echo ""
	@echo "SQS Queues:"
	aws --endpoint-url=http://localhost:4566 sqs list-queues --region us-east-1
	@echo ""
	@echo "SNS Topics:"
	aws --endpoint-url=http://localhost:4566 sns list-topics --region us-east-1

# Production
prod-build:
	docker build -t fastapi-aws-backend:latest .

prod-run:
	docker run -d \
		--name fastapi-app \
		-p 8000:8000 \
		--env-file .env.production \
		fastapi-aws-backend:latest

# Documentation
docs:
	@echo "API Documentation available at:"
	@echo "  http://localhost:8000/docs (Swagger UI)"
	@echo "  http://localhost:8000/redoc (ReDoc)"
	@echo "  http://localhost:8000/openapi.json (OpenAPI Spec)"

# SSL
ssl-generate:
	bash scripts/generate-ssl.sh

ssl-setup:
	bash scripts/ssl-setup.sh

ssl-renew:
	docker-compose exec certbot certbot renew --quiet
	docker-compose exec nginx nginx -s reload

ssl-test:
	@echo "Testing HTTPS..."
	curl -k https://localhost/health || true