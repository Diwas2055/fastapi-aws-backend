# AWS Architecture Overview

This document explains how all seven AWS services fit together in the FastAPI backend, the shared infrastructure (boto3 client setup, IAM, endpoints), and the event-driven flows that connect them.

## The Big Picture

```
                                    ┌────────────────────────────────────────────┐
                                    │                AWS Cloud                  │
                                    │                                            │
   HTTPS  ┌──────────────┐          │   ┌──────────────────────────────────┐     │
─────────▶│    ALB /      │────────▶│   │  FastAPI Service (ECS on Fargate) │    │
          │  Nginx (SSL)  │          │   │                                  │    │
          └──────────────┘          │   │  app/services/aws/*_service.py   │    │
                                    │   │                                  │    │
                                    │   │  ┌───────┐  ┌──────┐  ┌───────┐  │    │
                                    │   │  │  S3   │  │Dynamo│  │  SQS  │  │    │
                                    │   │  └───────┘  └──────┘  └───────┘  │    │
                                    │   │  ┌───────┐  ┌──────┐  ┌───────┐  │    │
                                    │   │  │  SNS  │  │Secrets│  │Lambda │  │    │
                                    │   │  └───────┘  └──────┘  └───────┘  │    │
                                    │   │  ┌────────────────────────────┐  │    │
                                    │   │  │        CloudWatch          │  │    │
                                    │   │  └────────────────────────────┘  │    │
                                    │   └──────────────────────────────────┘     │
                                    │                                            │
                                    │   ┌──────────┐  ┌───────┐  ┌───────────┐   │
                                    │   │PostgreSQL│  │ Redis │  │  Celery   │   │
                                    │   │ (RDS)    │  │(Elasti)│  │  Worker   │   │
                                    │   └──────────┘  └───────┘  └───────────┘   │
                                    └────────────────────────────────────────────┘
```

**Layers:**
1. **Edge** — ALB / Nginx terminates TLS, proxies to FastAPI (see `infrastructure/nginx/`).
2. **Application** — FastAPI app; all AWS access goes through the service classes in `app/services/aws/`.
3. **Data** — PostgreSQL (RDS, relational), DynamoDB (NoSQL/hot data), S3 (objects/files), Redis (cache/queues).
4. **Async** — Celery workers + SQS queue + SNS fan-out + Lambda reactions.
5. **Security** — Secrets Manager (vault), IAM roles (authN/Z), JWT (app authN).
6. **Observability** — CloudWatch (metrics, logs, alarms), structured logging.

## Shared AWS Client Setup

All services build on a shared **aioboto3** session configured once in `app/core/config.py`:

```python
# app/services/aws/__init__.py
from app.services.aws.s3_service import S3Service
# ... etc

s3_service            = S3Service()
dynamodb_service      = DynamoDBService()
sqs_service           = SQSService()
sns_service           = SNSService()
secrets_manager_service = SecretsManagerService()
lambda_service        = LambdaService()
cloudwatch_service    = CloudWatchService()
```

**One session, seven clients** — shared `AWS_REGION`, `AWS_ACCESS_KEY_ID`/`AWS_SECRET_ACCESS_KEY` (or role), and `AWS_ENDPOINT_URL` (LocalStack in dev):

| Setting | Dev | Production |
|---------|-----|-----------|
| `AWS_ENDPOINT_URL` | `http://localhost:4566` | *(unset)* → real AWS |
| Credentials | LocalStack dummy keys | IAM role (ECS task role) |
| Region | `us-east-1` | your deploy region |

## Routing & Access Control

All AWS endpoints live under `/api/v1/aws/*` and require a **superuser** JWT:

```
app/api/aws.py  →  APIRouter(prefix="/api/v1/aws", dependencies=[Depends(get_current_user), Depends(require_superuser)])
```

| Method | Path | Service |
|--------|------|---------|
| `POST` | `/aws/s3/bucket` | S3 |
| `GET` | `/aws/s3/files` | S3 |
| `GET` | `/aws/s3/files/{key}` | S3 |
| `DELETE` | `/aws/s3/files/{key}` | S3 |
| `POST` | `/aws/s3/upload-url` | S3 |
| `POST` | `/aws/dynamodb/table` | DynamoDB |
| `POST` | `/aws/dynamodb/items` | DynamoDB |
| `GET` | `/aws/dynamodb/items/{pk}/{sk}` | DynamoDB |
| `POST` | `/aws/dynamodb/query` | DynamoDB |
| `POST` | `/aws/sqs/send` | SQS |
| `POST` | `/aws/sqs/receive` | SQS |
| `POST` | `/aws/sns/publish` | SNS |
| `POST` | `/aws/secrets` | Secrets Manager |
| `GET` | `/aws/secrets/{name}` | Secrets Manager |
| `POST` | `/aws/lambda/invoke` | Lambda |
| `POST` | `/aws/cloudwatch/metric` | CloudWatch |
| `POST` | `/aws/cloudwatch/log` | CloudWatch |
| `GET` | `/aws/cloudwatch/logs` | CloudWatch |

Business-facing endpoints (items, users, auth) live under `/api/v1/items`, `/api/v1/users`, `/api/v1/auth` and are **not** superuser-gated.

## Event-Driven Flows

### Flow 1 — File upload → async processing (S3 + SQS + Celery)

```
POST /items/upload ──▶ S3 (store object)
        │
        └── SQS.send_message({key, item_id})          # async handoff
                │
                ▼
        Celery worker ── receive → process → delete message
```

### Flow 2 — Event fan-out (SNS → SQS + Lambda + email)

```
Item created ──▶ SNS.publish({event: "item.created"})
                      │ fan-out
        ┌─────────────┼───────────────────┐
        ▼             ▼                   ▼
     SQS queue    Lambda (thumbnail/      Email/SMS
     (Celery)      enrichment)            (user notify)
```

### Flow 3 — Secure bootstrap (Secrets Manager)

```
Container start ──▶ IAM role → SecretsManager.get_secret("fastapi/prod")
        └── DB password, JWT secret, API keys loaded into settings (cached)
```

### Flow 4 — Observability (CloudWatch)

```
Every request ──▶ structured JSON log ──▶ CloudWatch Logs
                     └── custom metrics (RequestCount, ErrorCount, latency) ──▶ Metrics + Alarms ──▶ SNS
```

### Flow 5 — Flexible hot data (DynamoDB)

```
POST /aws/dynamodb/items ──▶ put_item(pk, sk, data, gsi1pk, gsi1sk)
GET  /aws/dynamodb/items/{pk}/{sk} ──▶ get_item
POST /aws/dynamodb/query ──▶ query_items | query_gsi1 (indexes for alternative access)
```

## Production Deployment Map (docker-compose.prod.yml)

| Component | AWS Service | Notes |
|-----------|-------------|-------|
| FastAPI app | ECS on Fargate (or EKS) | Multi-stage Docker build, health checks |
| PostgreSQL | RDS | Managed, Multi-AZ, encrypted |
| Redis | ElastiCache | Celery broker + result backend |
| Object storage | S3 | `fastapi-uploads` bucket |
| NoSQL | DynamoDB | `fastapi-items` table + GSI1 |
| Queues | SQS | `fastapi-queue`, DLQ configured |
| Notifications | SNS | `fastapi-notifications` topic |
| Secrets | Secrets Manager | `fastapi/prod`, rotation via Lambda |
| Serverless | Lambda | thumbnail/reactor/export functions |
| Monitoring | CloudWatch | Logs, metrics, alarms → SNS |
| Load balancer | ALB + Nginx | TLS termination, `/health` probe |
| AuthN for AWS | IAM roles | Least-privilege per service (see each guide) |

## Cost & Performance Considerations

- **S3** — ~$0.023/GB/mo; use lifecycle rules to archive/expire old objects.
- **DynamoDB** — on-demand (`PAY_PER_REQUEST`) avoids idle costs; GSIs double write cost.
- **SQS** — long polling minimizes API calls; messages ≤ 256 KB.
- **SNS** — free per topic (pay per message + per subscriber endpoint).
- **Secrets Manager** — $0.40/secret/mo + rotation cost; cache reads.
- **Lambda** — pay per GB-second; keep functions short and small memory (128–512 MB typical).
- **CloudWatch** — metrics are cheap; logs/retention and custom metrics are where cost grows.

## Security Summary

| Layer | Control |
|-------|---------|
| Network | VPC + private subnets; ALB in public; services in private via VPC endpoints |
| IAM | One role per workload, least-privilege policies (see per-service guides) |
| Secrets | Secrets Manager with KMS + rotation; no secrets in images/repo |
| App | JWT auth; superuser gate on `/aws/*`; input validation via Pydantic |
| Data | S3 SSE + private buckets; DynamoDB encrypted at rest; RDS encryption |
| Observability | CloudTrail for audit; structured logging with no PII/secrets |

## Related Guides

- [S3 Guide](s3-guide.md) — file storage + presigned URLs
- [DynamoDB Guide](dynamodb-guide.md) — NoSQL + GSI design
- [SQS Guide](sqs-guide.md) — async message queue
- [SNS Guide](sns-guide.md) — pub/sub notifications
- [Secrets Manager Guide](secrets-manager-guide.md) — secure vault
- [Lambda Guide](lambda-guide.md) — serverless functions
- [CloudWatch Guide](cloudwatch-guide.md) — metrics, logs, alarms

---

[← Back to Docs Index](README.md)
