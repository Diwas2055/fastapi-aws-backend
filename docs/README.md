# AWS Services Documentation

Guides for every AWS service used in this project. Each guide explains what the service does, how to set it up, and how the app uses it.

## Services

| # | Service | File |
|---|---------|------|
| 1 | RDS (PostgreSQL) | [rds-guide.md](rds-guide.md) |
| 2 | S3 (file storage) | [s3-guide.md](s3-guide.md) |
| 3 | DynamoDB (NoSQL) | [dynamodb-guide.md](dynamodb-guide.md) |
| 4 | SQS (message queue) | [sqs-guide.md](sqs-guide.md) |
| 5 | SNS (notifications) | [sns-guide.md](sns-guide.md) |
| 6 | Secrets Manager | [secrets-manager-guide.md](secrets-manager-guide.md) |
| 7 | Lambda (serverless functions) | [lambda-guide.md](lambda-guide.md) |
| 8 | CloudWatch (logs and metrics) | [cloudwatch-guide.md](cloudwatch-guide.md) |
| 9 | LocalStack (local AWS) | [localstack-guide.md](localstack-guide.md) |
| 10 | SigNoz (observability) | [signoz-guide.md](signoz-guide.md) |
| 11 | Terraform (infrastructure) | [terraform-guide.md](terraform-guide.md) |
| 12 | Serverless (Lambda + API Gateway) | [serverless-guide.md](serverless-guide.md) |
| 13 | CI/CD Pipeline | [cicd-guide.md](cicd-guide.md) |
| 14 | All services together | [aws-architecture.md](aws-architecture.md) |

## Environment Variables by Service

| Service | Variables |
|---------|-----------|
| RDS | `DATABASE_URL`, `RDS_ENDPOINT`, `RDS_DB_NAME`, `RDS_USERNAME`, `RDS_PASSWORD` |
| S3 | `S3_BUCKET`, `S3_PRESIGNED_URL_EXPIRY`, `S3_MAX_FILE_SIZE` |
| DynamoDB | `DYNAMODB_TABLE`, `DYNAMODB_ENDPOINT_URL` |
| SQS | `SQS_QUEUE_URL`, `SQS_VISIBILITY_TIMEOUT` |
| SNS | `SNS_TOPIC_ARN` |
| Secrets Manager | `SECRETS_MANAGER_SECRET` |
| Lambda | `LAMBDA_FUNCTION_NAME` |
| CloudWatch | `CLOUDWATCH_LOG_GROUP`, `CLOUDWATCH_LOG_STREAM` |

## Where the Service Code Lives

```
app/services/aws/
├── s3_service.py            # S3Service - file storage
├── dynamodb_service.py      # DynamoDBService - NoSQL operations
├── sqs_service.py           # SQSService - message queue
├── sns_service.py           # SNSService - pub/sub notifications
├── secrets_service.py       # SecretsManagerService - secure secrets
├── lambda_service.py        # LambdaService - serverless invocation
├── cloudwatch_service.py    # CloudWatchService - metrics and logs
└── __init__.py              # Global service instances
```

## API Endpoints

All under `/api/v1/aws`. Require superuser JWT.

| Service | Endpoints |
|---------|-----------|
| S3 | `POST /s3/bucket`, `GET /s3/files`, `GET /s3/files/{key}`, `DELETE /s3/files/{key}`, `POST /s3/upload-url` |
| DynamoDB | `POST /dynamodb/table`, `POST /dynamodb/items`, `GET /dynamodb/items/{pk}/{sk}`, `POST /dynamodb/query` |
| SQS | `POST /sqs/send`, `POST /sqs/receive` |
| SNS | `POST /sns/publish` |
| Secrets Manager | `POST /secrets`, `GET /secrets/{name}` |
| Lambda | `POST /lambda/invoke`, `POST /lambda/functions`, `GET /lambda/functions`, `POST /lambda/functions/{id}/aliases`, `POST /lambda/functions/{id}/event-source-mappings`, `POST /lambda/layers`, `POST /lambda/functions/{id}/concurrency`, `POST /lambda/functions/{id}/permissions` |
| CloudWatch | `POST /cloudwatch/metric`, `POST /cloudwatch/log`, `GET /cloudwatch/logs` |

## Running Locally with LocalStack

All services work against LocalStack locally (no AWS account needed):

```bash
docker-compose up -d localstack
make aws-create-resources   # Creates S3 bucket, DynamoDB table, SQS queue, SNS topic
make aws-list-resources     # Lists all created resources
```

Set `AWS_ENDPOINT_URL=http://localhost:4566` in `.env` to point the app at LocalStack.

## CI/CD Pipeline

The project uses GitHub Actions for continuous integration and deployment. The pipeline runs automatically on every push and pull request.

**Workflow file**: [.github/workflows/ci-cd.yml](../.github/workflows/ci-cd.yml)
**Full guide**: [cicd-guide.md](cicd-guide.md)

### Pipeline Jobs

| Job | When It Runs | What It Does |
|-----|--------------|--------------|
| `lint` | Every push/PR | Runs ruff to check code style |
| `type-check` | Every push/PR | Runs mypy to check type hints |
| `test` | Every push/PR | Runs pytest with PostgreSQL and Redis |
| `security-scan` | Every push/PR | Checks for vulnerable dependencies |
| `docker-build` | Every push/PR | Builds Docker image to verify it works |
| `deploy` | Only on main branch | Pushes image to registry and deploys |
| `notify-on-failure` | If any job fails | Sends notification of failure |

### Required Secrets

Set these in GitHub repository settings under **Secrets and variables > Actions**:

- `DOCKER_REGISTRY` - Docker registry URL
- `DOCKER_USERNAME` - Registry username
- `DOCKER_PASSWORD` - Registry password
- `SSH_PRIVATE_KEY` - SSH key for deployment server
- `SSH_HOST` - Production server hostname/IP
- `SSH_USER` - SSH username

## Production Tips

- Use IAM roles instead of hardcoded credentials when running on AWS (ECS/EKS)
- Store secrets in Secrets Manager, not in `.env` files
- Use VPC endpoints so traffic stays inside AWS network
- Turn on backups and monitoring for production databases

→ Start with [aws-architecture.md](aws-architecture.md) for how everything connects, or open an individual service guide.
