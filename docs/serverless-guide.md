# Serverless Guide

## What It Is

Serverless is an architecture where you write individual functions that run in response to events, without managing servers. AWS Lambda is the compute layer, and API Gateway exposes those functions as HTTP endpoints.

In this project, "serverless" means:
- Lambda functions deployed independently from the main ECS app
- API Gateway routes that bypass the FastAPI app entirely
- Event-driven processing (S3, SQS, SNS triggers)

## Why We Use It

The FastAPI ECS app handles most traffic, but some paths benefit from serverless:

- **HTTP endpoints** — lightweight API routes that don't need the full FastAPI stack
- **Event processing** — react to S3 uploads, SQS messages, SNS notifications
- **Scheduled jobs** — cleanup, reports, reminders on a cron schedule
- **Variable traffic** — scale to zero when idle, no need for always-on ECS tasks
- **Cost efficiency** — pay only for actual execution time

## Architecture

```
Client
    │
    ├── FastAPI App (ECS) ──▶ Lambda (via boto3 invoke)
    │
    ├── API Gateway ──▶ Lambda (HTTP trigger)
    │
    └── AWS Events
            ├── S3 Event ──▶ Lambda
            ├── SQS Message ──▶ Lambda
            ├── SNS Notification ──▶ Lambda
            └── CloudWatch Schedule ──▶ Lambda
```

## Setup

### Prerequisites

```bash
# Install Serverless Framework
npm install -g serverless

# Install AWS credentials
aws configure

# Verify
serverless --version
```

### Configuration

1. **Install dependencies:**
```bash
cd infrastructure/serverless
npm install
```

2. **Deploy:**
```bash
# Deploy to dev
serverless deploy

# Deploy to staging
serverless deploy --stage staging

# Deploy to production
serverless deploy --stage production
```

3. **Test locally:**
```bash
serverless offline
```

## Functions

### 1. health

Simple health check endpoint.

**Trigger:** HTTP GET `/health`

**Response:**
```json
{
  "status": "healthy",
  "service": "fastapi-aws-backend-serverless",
  "timestamp": "2024-01-01T00:00:00.000Z"
}
```

### 2. webhook

HTTP webhook receiver for external integrations.

**Trigger:** HTTP POST `/webhook`

**Request:**
```json
{
  "type": "item.created",
  "payload": {
    "item_id": "123",
    "user_id": "456"
  }
}
```

**Response:**
```json
{
  "message": "Webhook processed successfully",
  "type": "item.created"
}
```

### 3. s3Processor

Automatically processes new S3 objects.

**Trigger:** S3 `ObjectCreated:*` on `uploads/` prefix, `.jpg` suffix

**Actions:**
- Extracts object metadata
- Stores metadata in DynamoDB
- Logs processing details

### 4. sqsProcessor

Processes messages from SQS queue.

**Trigger:** SQS message received

**Actions:**
- Parses message body
- Processes based on `action` field
- Acknowledges on success

### 5. snsProcessor

Handles SNS notifications.

**Trigger:** SNS message published

**Actions:**
- Parses notification
- Forwards to SQS for async processing
- Logs notification details

### 6. scheduledCleanup

Runs daily cleanup of old S3 objects.

**Trigger:** CloudWatch Events (daily schedule)

**Actions:**
- Lists objects in `temp/` prefix older than 7 days
- Deletes them
- Logs cleanup results

## Event Flow Examples

### Flow 1 — Webhook from External Service

```
External Service ──▶ API Gateway /webhook ──▶ Lambda (webhook)
                                                    │
                                                    ├── Store in DynamoDB
                                                    └── Return 200 OK
```

### Flow 2 — S3 Upload Processing

```
User uploads file ──▶ S3 (uploads/)
                          │
                          ▼
                    Lambda (s3Processor)
                          │
                          ├── Get metadata
                          ├── Store in DynamoDB
                          └── Log to CloudWatch
```

### Flow 3 — Async Processing via SQS

```
FastAPI App ──▶ SQS Queue
                    │
                    ▼
              Lambda (sqsProcessor)
                    │
                    ├── Process message
                    ├── Update DynamoDB
                    └── Return success
```

### Flow 4 — Notification Fan-Out

```
FastAPI App ──▶ SNS Topic
                    │
                    ├── SQS Queue ──▶ Lambda (sqsProcessor)
                    ├── Lambda (snsProcessor)
                    └── Email/SMS
```

### Flow 5 — Scheduled Cleanup

```
CloudWatch Events (daily)
                    │
                    ▼
              Lambda (scheduledCleanup)
                    │
                    └── Delete old S3 objects
```

## Configuration

### serverless.yml

| Setting | Description | Default |
|---------|-------------|---------|
| `provider.region` | AWS region | `us-east-1` |
| `provider.stage` | Deployment stage | `dev` |
| `provider.memorySize` | Lambda memory (MB) | `128` |
| `provider.timeout` | Lambda timeout (seconds) | `30` |
| `functions.health.memorySize` | Override for health function | Inherits from provider |
| `functions.sqsProcessor.batchSize` | SQS batch size | `10` |
| `functions.scheduledCleanup.rate` | Cron schedule | `rate(1 day)` |

### Environment Variables

| Variable | Description |
|----------|-------------|
| `AWS_NODEJS_CONNECTION_REUSE_ENABLED` | Reuse HTTP connections |
| `NODE_ENV` | Environment (dev/staging/production) |
| `DYNAMODB_TABLE` | DynamoDB table name |
| `S3_BUCKET` | S3 bucket name |
| `SQS_QUEUE_URL` | SQS queue URL |
| `SNS_TOPIC_ARN` | SNS topic ARN |

## Serverless vs ECS

| Aspect | Serverless (Lambda) | ECS (FastAPI) |
|--------|---------------------|---------------|
| Use case | Event-driven, variable traffic | Long-running APIs, persistent connections |
| Scaling | Automatic to zero | Manual or auto scaling (min 1) |
| Cost | Pay per invocation | Pay for always-on tasks |
| Cold start | Yes (mitigated with provisioned concurrency) | No |
| Max duration | 15 minutes | Unlimited |
| State | Stateless | Can maintain state |
| Language | Any supported runtime | Any (Docker) |

## Best Practices

1. **Keep functions small and focused** — one function per event type
2. **Use environment variables** for config, not hardcoded values
3. **Set appropriate timeouts** — don't leave at default 3 seconds
4. **Use provisioned concurrency** for latency-sensitive functions
5. **Enable Lambda Insights** for performance monitoring
6. **Use dead-letter queues** for async invocations
7. **Version functions** and use aliases for stable deployments
8. **Keep packages small** — fewer dependencies = faster cold starts
9. **Use layers** for shared dependencies across functions
10. **Monitor with CloudWatch** — set up alarms for errors and throttles

## CI/CD

Add to `.github/workflows/`:

```yaml
- name: Deploy Serverless Functions
  run: |
    cd infrastructure/serverless
    npm install
    serverless deploy --stage ${{ github.ref == 'refs/heads/main' && 'production' || 'dev' }}
```

## Local Development

```bash
# Start local Lambda + API Gateway
serverless offline

# Invoke function locally
serverless invoke local --function health

# View logs
serverless logs --function health

# Remove deployed functions
serverless remove
```

## Monitoring

- **CloudWatch Logs** — all Lambda logs
- **CloudWatch Metrics** — invocations, errors, duration, throttles
- **X-Ray** — distributed tracing (enable in serverless.yml)
- **SigNoz** — full APM if deployed

---

← Back to [Docs Index](README.md)
