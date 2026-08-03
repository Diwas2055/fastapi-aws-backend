# AWS Services Documentation

This folder contains detailed guides for every AWS service integrated into the FastAPI backend. Each guide covers the service's purpose, how it fits into the application, configuration, architecture, code usage, API endpoints, security, and best practices.

## Guide Index

| # | Service | Category | Guide |
|---|---------|----------|-------|
| 1 | **S3** | Storage | [S3 - File Storage Guide](s3-guide.md) |
| 2 | **DynamoDB** | Database | [DynamoDB - NoSQL Guide](dynamodb-guide.md) |
| 3 | **SQS** | Messaging | [SQS - Message Queue Guide](sqs-guide.md) |
| 4 | **SNS** | Messaging | [SNS - Notifications Guide](sns-guide.md) |
| 5 | **Secrets Manager** | Security | [Secrets Manager Guide](secrets-manager-guide.md) |
| 6 | **Lambda** | Compute | [Lambda - Serverless Guide](lambda-guide.md) |
| 7 | **CloudWatch** | Monitoring | [CloudWatch Guide](cloudwatch-guide.md) |
| 8 | **All Services** | Overview | [AWS Architecture Overview](aws-architecture.md) |

## Service Quick Reference

| Service | Service Class | Global Instance | Config Keys |
|---------|--------------|-----------------|-------------|
| S3 | `S3Service` | `s3_service` | `S3_BUCKET`, `S3_PRESIGNED_URL_EXPIRY` |
| DynamoDB | `DynamoDBService` | `dynamodb_service` | `DYNAMODB_TABLE`, `DYNAMODB_ENDPOINT_URL` |
| SQS | `SQSService` | `sqs_service` | `SQS_QUEUE_URL`, `SQS_VISIBILITY_TIMEOUT` |
| SNS | `SNSService` | `sns_service` | `SNS_TOPIC_ARN` |
| Secrets Manager | `SecretsManagerService` | `secrets_manager_service` | `SECRETS_MANAGER_SECRET` |
| Lambda | `LambdaService` | `lambda_service` | `LAMBDA_FUNCTION_NAME` |
| CloudWatch | `CloudWatchService` | `cloudwatch_service` | `CLOUDWATCH_LOG_GROUP`, `CLOUDWATCH_LOG_STREAM` |

## Where the Code Lives

```
app/services/aws/
├── s3_service.py            # S3Service - file storage
├── dynamodb_service.py      # DynamoDBService - NoSQL operations
├── sqs_service.py           # SQSService - message queue
├── sns_service.py           # SNSService - pub/sub notifications
├── secrets_service.py       # SecretsManagerService - secure secrets
├── lambda_service.py        # LambdaService - serverless invocation
├── cloudwatch_service.py    # CloudWatchService - metrics & logs
└── __init__.py              # Global service instances
```

## API Endpoints (all under `/api/v1/aws`, superuser only)

| Service | Endpoints |
|---------|-----------|
| S3 | `POST /s3/bucket`, `GET /s3/files`, `GET /s3/files/{key}`, `DELETE /s3/files/{key}`, `POST /s3/upload-url` |
| DynamoDB | `POST /dynamodb/table`, `POST /dynamodb/items`, `GET /dynamodb/items/{pk}/{sk}`, `POST /dynamodb/query` |
| SQS | `POST /sqs/send`, `POST /sqs/receive` |
| SNS | `POST /sns/publish` |
| Secrets Manager | `POST /secrets`, `GET /secrets/{name}` |
| Lambda | `POST /lambda/invoke` |
| CloudWatch | `POST /cloudwatch/metric`, `POST /cloudwatch/log`, `GET /cloudwatch/logs` |

## Development with LocalStack

All services can run against **LocalStack** locally (no AWS account needed):

```bash
docker-compose up -d localstack
make aws-create-resources   # Creates S3 bucket, DynamoDB table, SQS queue, SNS topic
make aws-list-resources     # Lists all created resources
```

Set `AWS_ENDPOINT_URL=http://localhost:4566` in `.env` to point the app at LocalStack.

## Production Notes

- **IAM**: Create scoped IAM roles with least-privilege policies per service (see each guide's IAM section).
- **Secrets**: Never store credentials in code or `.env` — use Secrets Manager (rotated) or IAM roles (ECS/EKS).
- **Networking**: Services communicate over VPC endpoints for private, secure traffic.
- **Costs**: S3/DynamoDB on-demand, CloudWatch metrics at 1-minute granularity, etc.

---

→ Continue to [AWS Architecture Overview](aws-architecture.md) for how everything connects, or open an individual guide.
