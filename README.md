# FastAPI AWS Backend

A production-ready FastAPI backend with comprehensive AWS service integrations, designed for modern backend development.

## Features

- **FastAPI** - Modern, fast web framework for building APIs
- **PostgreSQL** - Primary database with SQLAlchemy 2.0 async ORM
- **Redis** - Caching and Celery broker
- **JWT Authentication** - Access/refresh tokens with secure storage
- **AWS Services Integration**:
  - **S3** - File storage with presigned URLs
  - **DynamoDB** - NoSQL database with GSI support
  - **SQS** - Message queuing for async processing
  - **SNS** - Pub/Sub notifications
  - **Secrets Manager** - Secure secret storage
  - **Lambda** - Serverless function invocation
  - **CloudWatch** - Monitoring and logging
- **Celery** - Background task processing
- **Docker** - Multi-stage builds with docker-compose
- **Nginx** - Reverse proxy with SSL termination
- **Alembic** - Database migrations
- **Structured Logging** - JSON logging with structlog
- **Health Checks** - Kubernetes-ready probes

## Documentation

Detailed guides for every AWS service integration live in [`docs/`](docs/):

| Guide | Description |
|-------|-------------|
| [AWS Architecture Overview](docs/aws-architecture.md) | How all AWS services fit together, event flows, deployment map |
| [S3 Guide](docs/s3-guide.md) | File storage with presigned URLs |
| [DynamoDB Guide](docs/dynamodb-guide.md) | NoSQL database with GSI support |
| [SQS Guide](docs/sqs-guide.md) | Message queuing for async processing |
| [SNS Guide](docs/sns-guide.md) | Pub/Sub notifications |
| [Secrets Manager Guide](docs/secrets-manager-guide.md) | Secure secret storage |
| [Lambda Guide](docs/lambda-guide.md) | Serverless function invocation |
| [CloudWatch Guide](docs/cloudwatch-guide.md) | Monitoring and logging |

Each guide covers configuration, code usage, API endpoints, LocalStack setup, IAM policies, best practices, and common errors.

## Quick Start

### Prerequisites

- Docker and Docker Compose
- Python 3.12+ (for local development)
- AWS CLI (for production deployment)

### Development Setup

1. **Clone and navigate to the project:**
```bash
cd aws-fastapi-backend
```

2. **Copy environment file:**
```bash
cp .env.example .env
```

3. **Start all services:**
```bash
docker-compose up -d
```

4. **Verify services are running:**
```bash
docker-compose ps
```

5. **Access the API:**
- API: http://localhost:8000
- Docs: http://localhost:8000/docs
- Health: http://localhost:8000/health

### Local Development (without Docker)

1. **Create virtual environment:**
```bash
python -m venv .venv
source .venv/bin/activate  # On Windows: .venv\Scripts\activate
```

2. **Install dependencies:**
```bash
pip install -r requirements.txt
```

3. **Start PostgreSQL and Redis (using Docker):**
```bash
docker-compose up -d postgres redis localstack
```

4. **Run migrations:**
```bash
alembic upgrade head
```

5. **Start the application:**
```bash
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

6. **Start Celery worker (separate terminal):**
```bash
celery -A app.core.celery_app worker --loglevel=info
```

7. **Start Celery beat (separate terminal):**
```bash
celery -A app.core.celery_app beat --loglevel=info
```

## Project Structure

```
aws-fastapi-backend/
├── app/
│   ├── api/              # API routes
│   │   ├── auth.py       # Authentication endpoints
│   │   ├── users.py      # User management
│   │   ├── items.py      # Item CRUD with S3
│   │   ├── aws.py        # AWS service endpoints
│   │   └── health.py     # Health checks
│   ├── core/             # Core configuration
│   │   ├── config.py     # Settings management
│   │   ├── security.py   # JWT & password hashing
│   │   ├── logging.py    # Structured logging
│   │   └── celery_app.py # Celery configuration
│   ├── db/               # Database
│   │   └── session.py    # Async session management
│   ├── models/           # SQLAlchemy models
│   ├── schemas/          # Pydantic schemas
│   ├── services/         # Business logic
│   │   ├── aws/          # AWS service clients
│   │   │   ├── s3_service.py
│   │   │   ├── dynamodb_service.py
│   │   │   ├── sqs_service.py
│   │   │   ├── sns_service.py
│   │   │   ├── secrets_service.py
│   │   │   ├── lambda_service.py
│   │   │   └── cloudwatch_service.py
│   │   ├── user_service.py
│   │   └── tasks/        # Celery tasks
│   └── main.py           # FastAPI application
├── docs/                 # AWS service guides
│   ├── README.md         # Documentation index
│   ├── aws-architecture.md
│   ├── s3-guide.md
│   ├── dynamodb-guide.md
│   ├── sqs-guide.md
│   ├── sns-guide.md
│   ├── secrets-manager-guide.md
│   ├── lambda-guide.md
│   └── cloudwatch-guide.md
├── migrations/           # Alembic migrations
├── scripts/              # Database init scripts & utilities
├── infrastructure/       # Infrastructure configs
│   ├── nginx/            # Nginx configuration
│   └── ssl/              # SSL certificates
├── tests/                # Test suite
├── Dockerfile            # Multi-stage Docker build
├── docker-compose.yml    # Service orchestration (dev)
├── docker-compose.prod.yml # Production override
├── requirements.txt      # Python dependencies
├── pyproject.toml        # Modern Python packaging
├── alembic.ini           # Alembic configuration
├── pytest.ini            # Pytest configuration
├── Makefile              # Common development commands
├── .pre-commit-config.yaml # Pre-commit hooks
├── .env.example          # Environment template
└── .env.production.example # Production environment template
```

## API Endpoints

### Authentication
| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/api/v1/auth/register` | Register new user |
| POST | `/api/v1/auth/login` | Login & get tokens |
| POST | `/api/v1/auth/refresh` | Refresh access token |
| POST | `/api/v1/auth/logout` | Logout (revoke token) |
| POST | `/api/v1/auth/logout-all` | Logout from all devices |
| GET | `/api/v1/auth/me` | Get current user |
| PUT | `/api/v1/auth/me` | Update current user |

### Users (Superuser only)
| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/v1/users` | List users (paginated) |
| GET | `/api/v1/users/{id}` | Get user by ID |
| PUT | `/api/v1/users/{id}` | Update user |
| DELETE | `/api/v1/users/{id}` | Delete user |

### Items
| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/api/v1/items` | Create item |
| GET | `/api/v1/items` | List user's items |
| GET | `/api/v1/items/{id}` | Get item |
| GET | `/api/v1/items/{id}/download` | Get item with download URL |
| PUT | `/api/v1/items/{id}` | Update item |
| DELETE | `/api/v1/items/{id}` | Delete item |
| POST | `/api/v1/items/{id}/upload-url` | Get S3 presigned upload URL |
| POST | `/api/v1/items/upload` | Direct file upload |

### AWS Services (Superuser only)
| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/api/v1/aws/s3/bucket` | Create S3 bucket |
| GET | `/api/v1/aws/s3/files` | List S3 files |
| POST | `/api/v1/aws/s3/upload-url` | Get S3 presigned URL |
| POST | `/api/v1/aws/dynamodb/table` | Create DynamoDB table |
| POST | `/api/v1/aws/dynamodb/items` | Put DynamoDB item |
| POST | `/api/v1/aws/sqs/send` | Send SQS message |
| POST | `/api/v1/aws/sns/publish` | Publish SNS message |
| POST | `/api/v1/aws/secrets` | Create secret |
| POST | `/api/v1/aws/lambda/invoke` | Invoke Lambda |
| POST | `/api/v1/aws/cloudwatch/metric` | Put custom metric |

### Health Checks
| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/health` | Basic health check |
| GET | `/health/detailed` | Detailed health with dependencies |
| GET | `/ready` | Kubernetes readiness probe |
| GET | `/live` | Kubernetes liveness probe |

## AWS Services Usage

### S3 - File Storage

```python
from app.services.aws import s3_service

# Generate presigned upload URL
key = s3_service.generate_unique_key("document.pdf", "uploads/user123")
url = await s3_service.generate_presigned_upload_url(key, "application/pdf")

# Upload file
await s3_service.upload_file(file_obj, key, "application/pdf")

# Generate download URL
download_url = await s3_service.generate_presigned_download_url(key)
```

### DynamoDB - NoSQL

```python
from app.services.aws import dynamodb_service

# Put item with GSI
await dynamodb_service.put_item(
    pk="USER#123",
    sk="ITEM#456",
    data={"name": "Product", "price": 29.99},
    gsi1pk="CATEGORY#electronics",
    gsi1sk="PRICE#29.99"
)

# Query by partition key
items = await dynamodb_service.query_items(pk="USER#123", sk_prefix="ITEM#")

# Query GSI
items = await dynamodb_service.query_gsi1(gsi1pk="CATEGORY#electronics")
```

### SQS - Message Queue

```python
from app.services.aws import sqs_service

# Send message
await sqs_service.send_message(
    message_body={"action": "process", "item_id": "123"},
    delay_seconds=30
)

# Receive and process messages
messages = await sqs_service.receive_messages(max_messages=10)
for msg in messages:
    # Process message
    await sqs_service.delete_message(msg["ReceiptHandle"])
```

### SNS - Notifications

```python
from app.services.aws import sns_service

# Publish notification
await sns_service.publish(
    message="New item created",
    subject="Item Created",
    message_attributes={
        "item_id": {"DataType": "String", "StringValue": "123"}
    }
)

# Subscribe endpoint
await sns_service.subscribe(
    protocol="email",
    endpoint="user@example.com",
    filter_policy={"item_type": ["product", "service"]}
)
```

### Secrets Manager

```python
from app.services.aws import secrets_manager_service

# Store secret
await secrets_manager_service.create_secret(
    name="prod/database",
    secret_value={"username": "admin", "password": "secret123"},
    description="Production database credentials"
)

# Retrieve secret
creds = await secrets_manager_service.get_secret("prod/database")
```

### CloudWatch - Monitoring

```python
from app.services.aws import cloudwatch_service

# Put custom metric
await cloudwatch_service.put_metric(
    namespace="MyApp",
    name="ItemsCreated",
    value=1,
    unit="Count",
    dimensions=[{"Name": "Environment", "Value": "production"}]
)

# Put log event
await cloudwatch_service.put_log_event(
    message="User login successful",
    level="INFO"
)
```

## Database Migrations

```bash
# Create new migration
alembic revision --autogenerate -m "description"

# Apply migrations
alembic upgrade head

# Rollback
alembic downgrade -1

# Show history
alembic history
```

## Testing

```bash
# Run tests
pytest

# Run with coverage
pytest --cov=app --cov-report=html

# Run specific test
pytest tests/test_auth.py -v
```

## Development Commands

Use the Makefile for common development tasks:

```bash
# Show all available commands
make help

# Development
make install      # Install dependencies
make dev          # Run dev server with reload
make worker       # Run Celery worker
make beat         # Run Celery beat scheduler
make shell        # Open Python shell with app context

# Testing
make test         # Run all tests
make test-cov     # Run tests with coverage report
make test-unit    # Run unit tests only
make test-integration  # Run integration tests only

# Code Quality
make lint         # Run ruff + mypy
make format       # Auto-format code with ruff
make type-check   # Run mypy type checking

# Database
make migrate-up       # Apply all migrations
make migrate-down     # Rollback last migration
make migrate-new      # Create new migration (interactive)
make migrate-history  # Show migration history
make db-reset         # Reset database (downgrade + upgrade)

# Docker
make docker-up        # Start all services
make docker-down      # Stop all services
make docker-down-v    # Stop and remove volumes
make docker-logs      # View all logs
make docker-logs-app  # View app logs only
make docker-build     # Build Docker image
make docker-rebuild   # Rebuild without cache
make docker-shell     # Shell into app container
make docker-db-shell  # PostgreSQL shell
make docker-redis-shell  # Redis CLI

# AWS LocalStack
make aws-create-resources  # Create S3, DynamoDB, SQS, SNS in LocalStack
make aws-list-resources    # List all LocalStack resources

# Production
make prod-build   # Build production Docker image
make prod-run     # Run production container locally

# Utilities
make clean        # Clean all cache files
make docs         # Show documentation URLs
```

## LocalStack Development

LocalStack provides a local AWS cloud stack for development/testing:

```bash
# Start LocalStack (included in docker-compose)
docker-compose up -d localstack

# Verify LocalStack is ready
curl http://localhost:4566/_localstack/health

# Create AWS resources
make aws-create-resources

# List created resources
make aws-list-resources

# Use AWS CLI with LocalStack
aws --endpoint-url=http://localhost:4566 s3 ls
aws --endpoint-url=http://localhost:4566 dynamodb list-tables --region us-east-1
aws --endpoint-url=http://localhost:4566 sqs list-queues --region us-east-1
aws --endpoint-url=http://localhost:4566 sns list-topics --region us-east-1
```

### LocalStack Service Endpoints

| Service | Endpoint | Example |
|---------|----------|---------|
| S3 | http://localhost:4566 | `aws --endpoint-url=http://localhost:4566 s3 mb s3://my-bucket` |
| DynamoDB | http://localhost:4566 | `aws --endpoint-url=http://localhost:4566 dynamodb create-table ...` |
| SQS | http://localhost:4566 | `aws --endpoint-url=http://localhost:4566 sqs create-queue ...` |
| SNS | http://localhost:4566 | `aws --endpoint-url=http://localhost:4566 sns create-topic ...` |
| Secrets Manager | http://localhost:4566 | `aws --endpoint-url=http://localhost:4566 secretsmanager create-secret ...` |
| Lambda | http://localhost:4566 | `aws --endpoint-url=http://localhost:4566 lambda invoke ...` |
| CloudWatch | http://localhost:4566 | `aws --endpoint-url=http://localhost:4566 cloudwatch put-metric-data ...` |

## Pre-commit Hooks

Automated code quality checks on commit:

```bash
# Install hooks
pre-commit install

# Run manually
pre-commit run --all-files

# Update hooks
pre-commit autoupdate
```

Hooks included:
- **Ruff** - Fast linting & formatting
- **MyPy** - Static type checking
- **Bandit** - Security linting
- **detect-secrets** - Secret detection
- **Standard hooks** - YAML/JSON/TOML validation, merge conflicts, large files

## Useful Scripts

```bash
# Generate self-signed SSL certificates for local HTTPS
./scripts/generate-ssl.sh

# Initialize database (run in Docker)
docker-compose exec app python -m scripts.init_db
```

## Testing

```bash
# Run all tests
pytest

# Run with coverage
pytest --cov=app --cov-report=html --cov-report=term

# Run specific test file
pytest tests/test_auth.py -v

# Run tests with specific marker
pytest -m unit -v           # Unit tests only
pytest -m integration -v    # Integration tests only
pytest -m "not slow" -v     # Skip slow tests

# Run in watch mode (requires pytest-watch)
pytest-watch -v
```

### Test Structure

```
tests/
├── conftest.py           # Shared fixtures & configuration
├── test_health.py        # Health endpoint tests
├── test_auth.py          # Authentication tests
└── test_*.py             # Additional test files
```

### Test Fixtures

- `client` - Async HTTP client with test database
- `db_session` - Fresh database session per test
- `test_user` - Regular user fixture
- `superuser` - Superuser fixture
- `auth_headers` - Authorization headers for test user
- `superuser_headers` - Authorization headers for superuser

## Deployment

### Production Docker Build

```bash
# Build production image
docker build -t fastapi-aws-backend:latest .

# Run with production config
docker-compose -f docker-compose.yml -f docker-compose.prod.yml up -d
```

### Environment Variables for Production

```bash
# Required
SECRET_KEY=your-secure-random-key
DATABASE_URL=postgresql+asyncpg://user:pass@host:5432/db
REDIS_URL=redis://host:6379/0
AWS_ACCESS_KEY_ID=your-access-key
AWS_SECRET_ACCESS_KEY=your-secret-key
AWS_REGION=us-east-1

# AWS Resources (create beforehand)
S3_BUCKET=myapp-uploads
DYNAMODB_TABLE=myapp-items
SQS_QUEUE_URL=https://sqs.region.amazonaws.com/account/queue
SNS_TOPIC_ARN=arn:aws:sns:region:account:topic
```

### Kubernetes Deployment

Key considerations:
- Use the `/ready` and `/live` endpoints for probes
- Configure HPA based on CPU/memory or custom metrics
- Use AWS Load Balancer Controller for ALB
- Store secrets in AWS Secrets Manager or Kubernetes Secrets
- Enable CloudWatch Container Insights

### CI/CD Pipeline

```yaml
# Example GitHub Actions workflow
name: Deploy
on:
  push:
    branches: [main]
jobs:
  deploy:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - name: Build and push
        run: |
          docker build -t ${{ secrets.ECR_REGISTRY }}/fastapi-backend:${{ github.sha }} .
          docker push ${{ secrets.ECR_REGISTRY }}/fastapi-backend:${{ github.sha }}
      - name: Deploy to ECS
        run: |
          aws ecs update-service --cluster production --service fastapi-backend --force-new-deployment
```

## Security Best Practices

1. **Secrets Management**: Never commit `.env` files. Use AWS Secrets Manager or Kubernetes Secrets.
2. **HTTPS**: Always use TLS in production. Nginx handles SSL termination.
3. **CORS**: Configure `CORS_ORIGINS` for your specific domains.
4. **Rate Limiting**: Nginx and application-level rate limiting protect against abuse.
5. **Token Security**: Short-lived access tokens (30 min), longer refresh tokens (7 days).
6. **Password Hashing**: Bcrypt with configurable rounds.
7. **SQL Injection**: SQLAlchemy ORM prevents injection.
8. **Dependencies**: Regularly update with `pip-audit` or `safety`.

## Monitoring & Observability

- **Health Checks**: `/health`, `/ready`, `/live`
- **Metrics**: Custom CloudWatch metrics via `/api/v1/aws/cloudwatch/metric`
- **Logging**: Structured JSON logs sent to CloudWatch
- **Tracing**: Add OpenTelemetry for distributed tracing
- **Alerting**: CloudWatch alarms for error rates, latency, etc.

## Environment Variables Reference

### Application
| Variable | Default | Description |
|----------|---------|-------------|
| `APP_NAME` | FastAPI AWS Backend | Application name |
| `APP_VERSION` | 1.0.0 | Application version |
| `ENVIRONMENT` | development | Environment (development/staging/production) |
| `DEBUG` | true | Enable debug mode |
| `API_V1_PREFIX` | /api/v1 | API version prefix |

### Server
| Variable | Default | Description |
|----------|---------|-------------|
| `HOST` | 0.0.0.0 | Server host |
| `PORT` | 8000 | Server port |
| `WORKERS` | 4 | Worker processes (production) |

### Security
| Variable | Default | Description |
|----------|---------|-------------|
| `SECRET_KEY` | auto-generated | JWT signing key (CHANGE IN PRODUCTION!) |
| `ALGORITHM` | HS256 | JWT algorithm |
| `ACCESS_TOKEN_EXPIRE_MINUTES` | 30 | Access token lifetime |
| `REFRESH_TOKEN_EXPIRE_DAYS` | 7 | Refresh token lifetime |
| `PASSWORD_MIN_LENGTH` | 8 | Minimum password length |

### Database
| Variable | Default | Description |
|----------|---------|-------------|
| `DATABASE_URL` | postgresql+asyncpg://postgres:postgres@localhost:5432/fastapi_app | Async database URL |
| `DATABASE_POOL_SIZE` | 10 | Connection pool size |
| `DATABASE_MAX_OVERFLOW` | 20 | Max overflow connections |
| `DATABASE_POOL_TIMEOUT` | 30 | Pool timeout (seconds) |

### Redis
| Variable | Default | Description |
|----------|---------|-------------|
| `REDIS_URL` | redis://localhost:6379/0 | Redis connection URL |
| `REDIS_MAX_CONNECTIONS` | 50 | Max connections |
| `REDIS_SOCKET_TIMEOUT` | 5 | Socket timeout |
| `REDIS_SOCKET_CONNECT_TIMEOUT` | 5 | Connect timeout |

### AWS
| Variable | Default | Description |
|----------|---------|-------------|
| `AWS_REGION` | us-east-1 | AWS region |
| `AWS_ACCESS_KEY_ID` | - | AWS access key |
| `AWS_SECRET_ACCESS_KEY` | - | AWS secret key |
| `AWS_ENDPOINT_URL` | http://localhost:4566 | LocalStack endpoint (dev) |

### S3
| Variable | Default | Description |
|----------|---------|-------------|
| `S3_BUCKET` | fastapi-uploads | S3 bucket name |
| `S3_PRESIGNED_URL_EXPIRY` | 3600 | Presigned URL expiry (seconds) |
| `S3_MAX_FILE_SIZE` | 10485760 | Max file size (10MB) |

### DynamoDB
| Variable | Default | Description |
|----------|---------|-------------|
| `DYNAMODB_TABLE` | fastapi-items | Table name |
| `DYNAMODB_ENDPOINT_URL` | http://localhost:4566 | LocalStack endpoint |

### SQS
| Variable | Default | Description |
|----------|---------|-------------|
| `SQS_QUEUE_URL` | http://localhost:4566/.../fastapi-queue | Queue URL |
| `SQS_VISIBILITY_TIMEOUT` | 300 | Visibility timeout (seconds) |
| `SQS_MAX_RECEIVE_COUNT` | 3 | Max receive count |

### SNS
| Variable | Default | Description |
|----------|---------|-------------|
| `SNS_TOPIC_ARN` | arn:aws:sns:...:fastapi-notifications | Topic ARN |

### Secrets Manager
| Variable | Default | Description |
|----------|---------|-------------|
| `SECRETS_MANAGER_SECRET` | fastapi/secrets | Secret name |

### Lambda
| Variable | Default | Description |
|----------|---------|-------------|
| `LAMBDA_FUNCTION_NAME` | - | Function name |

### CloudWatch
| Variable | Default | Description |
|----------|---------|-------------|
| `CLOUDWATCH_LOG_GROUP` | /aws/fastapi/app | Log group name |
| `CLOUDWATCH_LOG_STREAM` | application | Log stream name |

### CORS
| Variable | Default | Description |
|----------|---------|-------------|
| `CORS_ORIGINS` | ["http://localhost:3000", ...] | Allowed origins |
| `CORS_ALLOW_CREDENTIALS` | true | Allow credentials |
| `CORS_ALLOW_METHODS` | ["*"] | Allowed methods |
| `CORS_ALLOW_HEADERS` | ["*"] | Allowed headers |

### Rate Limiting
| Variable | Default | Description |
|----------|---------|-------------|
| `RATE_LIMIT_REQUESTS` | 100 | Requests per window |
| `RATE_LIMIT_WINDOW` | 60 | Window (seconds) |

### Logging
| Variable | Default | Description |
|----------|---------|-------------|
| `LOG_LEVEL` | INFO | Log level |
| `LOG_FORMAT` | json | Log format (json/console) |

### Celery
| Variable | Default | Description |
|----------|---------|-------------|
| `CELERY_BROKER_URL` | redis://localhost:6379/0 | Broker URL |
| `CELERY_RESULT_BACKEND` | redis://localhost:6379/0 | Result backend |

## Troubleshooting

### Common Issues

**1. Database connection failed**
```bash
# Check if PostgreSQL is running
docker-compose ps postgres

# Check logs
docker-compose logs postgres

# Verify connection
docker-compose exec app python -c "from app.db.session import engine; print('OK')"
```

**2. Redis connection failed**
```bash
# Check if Redis is running
docker-compose ps redis

# Test connection
docker-compose exec redis redis-cli ping
```

**3. LocalStack not ready**
```bash
# Wait for LocalStack health check
docker-compose logs localstack

# Check health endpoint
curl http://localhost:4566/_localstack/health
```

**4. Migration errors**
```bash
# Check current migration
alembic current

# Show history
alembic history

# Reset and reapply
make db-reset
```

**5. Port conflicts**
```bash
# Check what's using port 8000
lsof -i :8000

# Use different port
PORT=8001 uvicorn app.main:app --reload
```

**6. Permission denied (Docker)**
```bash
# Fix file permissions
sudo chown -R $USER:$USER .

# Or run with sudo (not recommended)
sudo docker-compose up -d
```

### Debug Mode

Enable debug logging:
```bash
# In .env
LOG_LEVEL=DEBUG
LOG_FORMAT=console
DEBUG=true
```

### Health Check Failures

```bash
# Check detailed health
curl http://localhost:8000/health/detailed

# Check individual services
curl http://localhost:8000/ready
curl http://localhost:8000/live
```

## Contributing

1. Fork the repository
2. Create feature branch
3. Make changes with tests
4. Run linting: `make lint`
5. Run type checking: `make type-check`
6. Run tests: `make test`
7. Submit PR

## License

MIT License - see LICENSE file for details.

---

## Quick Reference

### API Documentation
- **Swagger UI**: http://localhost:8000/docs
- **ReDoc**: http://localhost:8000/redoc
- **OpenAPI JSON**: http://localhost:8000/openapi.json

### Default Credentials (Development)
- **PostgreSQL**: postgres / postgres
- **Redis**: password: redis (if set)
- **LocalStack**: test / test

### Useful URLs
- **API Base**: http://localhost:8000/api/v1
- **Health**: http://localhost:8000/health
- **LocalStack**: http://localhost:4566
- **AWS Guides**: [`docs/`](docs/README.md) — full service documentation index