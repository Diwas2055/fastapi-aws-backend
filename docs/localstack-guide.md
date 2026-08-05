# LocalStack — Run AWS Services Locally

## What It Is

LocalStack is a tool that runs fake AWS services on your computer. It lets you develop and test AWS features without an AWS account or internet connection. It runs in Docker and listens on port 4566.

## Why We Use It

In this project, LocalStack lets you:
- Run the app without AWS credentials
- Test S3, DynamoDB, SQS, SNS, Lambda, Secrets Manager, CloudWatch locally
- Avoid AWS costs while developing
- Iterate quickly without deploying to AWS

## How It Works

LocalStack starts a local server that looks like AWS. The app connects to it the same way it would connect to real AWS, just with a different endpoint URL.

```
App ──▶ http://localstack:4566 ──▶ LocalStack ──▶ fake S3, DynamoDB, SQS, etc.
```

Real AWS uses URLs like `https://s3.amazonaws.com`. LocalStack uses `http://localstack:4566`.

## Setup

### Prerequisite: LocalStack Auth Token

LocalStack requires an auth token. Get one free at https://app.localstack.cloud/account/auth-tokens

```bash
# .env
LOCALSTACK_AUTH_TOKEN=your-token-here
```

Without this token, LocalStack will fail to start.

### Start LocalStack

```bash
docker-compose up -d localstack
```

This starts the `localstack` service defined in `docker-compose.yml`.

### Environment Variables

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `LOCALSTACK_AUTH_TOKEN` | Yes | - | Auth token from app.localstack.cloud |
| `LOCALSTACK_DOCKER_NAME` | No | `localstack-main` | Container name |
| `LOCALSTACK_VOLUME_DIR` | No | `./volume` | Local directory for LocalStack data |
| `DEBUG` | No | `0` | Debug mode (0 or 1) |
| `PERSISTENCE` | No | `0` | Persist data between restarts (0 or 1) |

### Check It's Running

```bash
# Health check
curl http://localhost:4566/_localstack/health

# List active services
curl http://localhost:4566/_localstack/health | jq .
```

You should see JSON with services like `s3`, `dynamodb`, `sqs`, etc. showing `available` or `running`.

### Stop LocalStack

```bash
docker-compose stop localstack
docker-compose rm localstack  # removes container
```

## Using LocalStack with This App

### 1. Start Everything

```bash
docker-compose up -d
```

This starts postgres, redis, localstack, and the app together.

### 2. Create AWS Resources

LocalStack starts empty. You need to create the same resources the app expects:

```bash
make aws-create-resources
```

This runs a script that creates:
- S3 bucket: `fastapi-uploads`
- DynamoDB table: `fastapi-items`
- SQS queue: `fastapi-queue`
- SNS topic: `fastapi-notifications`

List what was created:

```bash
make aws-list-resources
```

### 3. Use the App

The app already points to LocalStack via these env vars in `docker-compose.yml`:

```env
AWS_ENDPOINT_URL=http://localstack:4566
AWS_ACCESS_KEY_ID=test
AWS_SECRET_ACCESS_KEY=test
AWS_REGION=us-east-1
```

You don't need to change anything. Just use the app normally.

## Using the AWS CLI with LocalStack

You can interact with LocalStack directly using the AWS CLI:

```bash
# S3 - list buckets
aws --endpoint-url=http://localhost:4566 s3 ls

# S3 - create bucket
aws --endpoint-url=http://localhost:4566 s3 mb s3://fastapi-uploads

# DynamoDB - list tables
aws --endpoint-url=http://localhost:4566 dynamodb list-tables

# SQS - list queues
aws --endpoint-url=http://localhost:4566 sqs list-queues

# SNS - list topics
aws --endpoint-url=http://localhost:4566 sns list-topics

# Secrets Manager - list secrets
aws --endpoint-url=http://localhost:4566 secretsmanager list-secrets

# CloudWatch - list metrics
aws --endpoint-url=http://localhost:4566 cloudwatch list-metrics
```

## Creating Resources Manually

If you need to create resources outside of `make aws-create-resources`:

### S3 Bucket

```bash
aws --endpoint-url=http://localhost:4566 s3 mb s3://fastapi-uploads
```

### DynamoDB Table

```bash
aws --endpoint-url=http://localhost:4566 dynamodb create-table \
    --table-name fastapi-items \
    --attribute-definitions AttributeName=pk,AttributeType=S AttributeName=sk,AttributeType=S \
    --key-schema AttributeName=pk,KeyType=HASH AttributeName=sk,KeyType=RANGE \
    --billing-mode PAY_PER_REQUEST \
    --region us-east-1
```

### SQS Queue

```bash
aws --endpoint-url=http://localhost:4566 sqs create-queue \
    --queue-name fastapi-queue \
    --region us-east-1
```

### SNS Topic

```bash
aws --endpoint-url=http://localhost:4566 sns create-topic \
    --name fastapi-notifications \
    --region us-east-1
```

### Secrets Manager Secret

```bash
aws --endpoint-url=http://localhost:4566 secretsmanager create-secret \
    --name fastapi/secrets \
    --secret-string '{"DB_PASSWORD":"test"}' \
    --region us-east-1
```

## Data Persistence

LocalStack data is stored in a Docker volume called `localstack_data`. This means:
- Data survives container restarts
- Data is deleted when you run `docker-compose down -v`
- Data is isolated to your machine

To completely reset LocalStack (delete all data):

```bash
docker-compose down -v
docker-compose up -d localstack
make aws-create-resources
```

## Configuration

### Change Port

If port 4566 is already in use, change it in `docker-compose.yml`:

```yaml
localstack:
  ports:
    - "9999:4566"  # access on http://localhost:9999
```

Then update the app's `AWS_ENDPOINT_URL` to `http://localstack:4566` (the internal container port stays 4566, only the host port changes).

### Enable More Services

Edit `docker-compose.yml` to add more AWS services:

```yaml
environment:
  - SERVICES=s3,dynamodb,sqs,sns,secretsmanager,lambda,cloudwatch,iam,sts,ec2,lambda
```

### Debug Mode

Debug mode is enabled in `docker-compose.yml`:

```yaml
environment:
  - DEBUG=1
```

This gives more detailed logs. Turn it off for faster startup:

```yaml
environment:
  - DEBUG=0
```

## How the App Uses LocalStack

The app uses the official AWS SDK (boto3/aioboto3). It connects to whatever endpoint you specify.

```python
# app/core/config.py
AWS_ENDPOINT_URL: Optional[str] = None  # set to http://localhost:4566 for LocalStack
```

When `AWS_ENDPOINT_URL` is set, all AWS services redirect to that endpoint instead of real AWS.

## Common Errors

| Error | Cause | Fix |
|-------|-------|-----|
| `Connection refused` on port 4566 | LocalStack not running | Start with `docker-compose up -d localstack` |
| `Service not available` | Service not enabled in LocalStack | Add service to `SERVICES` env var |
| `ResourceNotFoundException` | Resource not created | Run `make aws-create-resources` |
| `InvalidAccessKeyId` | Wrong credentials | Use `AWS_ACCESS_KEY_ID=test` and `AWS_SECRET_ACCESS_KEY=test` |
| Slow startup | Too many services enabled | Disable services you don't need in `SERVICES` env var |
| Out of memory | LocalStack needs RAM | Allocate at least 2GB RAM to Docker |

## LocalStack vs Real AWS

| Feature | LocalStack | Real AWS |
|---------|-----------|----------|
| Cost | Free | Pay per use |
| Speed | Fast (local) | Network latency |
| Setup | Docker only | AWS account needed |
| Data | Lost on volume delete | Persistent |
| Accuracy | Mostly compatible | Exact |
| Best for | Development, testing | Production |

## Troubleshooting

### Check Logs

```bash
docker-compose logs localstack
```

### Restart LocalStack

```bash
docker-compose restart localstack
```

### Clear All Data

```bash
docker-compose down -v
docker-compose up -d localstack
```

### Check Health Endpoint

```bash
curl http://localhost:4566/_localstack/health
```

## Next Steps

- Read individual service guides (S3, DynamoDB, etc.) for LocalStack-specific tips
- Read `aws-architecture.md` for how LocalStack fits in the overall system
- When ready for production, remove `AWS_ENDPOINT_URL` and use real AWS credentials

---

← Back to [Docs Index](README.md)
