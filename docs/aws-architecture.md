# AWS Architecture Overview

How the AWS services in this project fit together, shared infrastructure, and the event flows between them.

## System Layout

```
                                    ┌────────────────────────────────────────────┐
                                    │                AWS Cloud                  │
                                    │                                            │
   HTTPS  ┌──────────────┐          │   ┌──────────────────────────────────┐     │
─────────▶│    ALB /      │────────▶│   │  FastAPI Service (ECS on Fargate) │     │
         │  Nginx (SSL)  │          │   │                                  │     │
         └──────────────┘          │   │  app/services/aws/*_service.py   │     │
                                    │   │                                  │     │
                                    │   │  ┌───────┐  ┌──────┐  ┌───────┐  │     │
                                    │   │  │  S3   │  │Dynamo│  │  SQS  │  │     │
                                    │   │  └───────┘  └──────┘  └───────┘  │     │
                                    │   │  ┌───────┐  ┌──────┐  ┌───────┐  │     │
                                    │   │  │  SNS  │  │Secrets│  │Lambda │  │     │
                                    │   │  └───────┘  └──────┘  └───────┘  │     │
                                     │   │  ┌────────────────────────────┐  │     │
                                     │   │  │        CloudWatch          │  │     │
                                     │   │  └────────────────────────────┘  │     │
                                     │   │  ┌────────────────────────────┐  │     │
                                     │   │  │          SigNoz            │  │     │
                                     │   │  │   (Traces, Metrics, Logs)  │  │     │
                                     │   │  └────────────────────────────┘  │     │
                                     │   └──────────────────────────────────┘     │
                                    │                                            │
                                    │   ┌──────────┐  ┌───────┐  ┌───────────┐   │
                                    │   │PostgreSQL│  │ Redis │  │  Celery   │   │
                                    │   │ (RDS)    │  │(Elasti)│  │  Worker   │   │
                                    │   └──────────┘  └───────┘  └───────────┘   │
                                    └────────────────────────────────────────────┘
```

## Layers

1. **Edge** — ALB / Nginx handles HTTPS, proxies to FastAPI (see `infrastructure/nginx/`).
2. **Application** — FastAPI app; all AWS calls go through service classes in `app/services/aws/`.
3. **Data** — PostgreSQL (RDS, relational), DynamoDB (NoSQL/hot data), S3 (objects/files), Redis (cache/queues).
4. **Async** — Celery workers + SQS queue + SNS fan-out + Lambda reactions.
5. **Security** — Secrets Manager (vault), IAM roles (AWS access), JWT (app access).
6. **Observability** — CloudWatch (AWS metrics, logs, alarms), SigNoz (OpenTelemetry traces, metrics, logs, APM).

## Shared AWS Client Setup

All services use one shared aioboto3 session configured in `app/core/config.py`:

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

One session, seven clients. Shared `AWS_REGION`, `AWS_ACCESS_KEY_ID`/`AWS_SECRET_ACCESS_KEY` (or IAM role), and `AWS_ENDPOINT_URL` (LocalStack in dev):

| Setting | Dev | Production |
|---------|-----|-----------|
| `AWS_ENDPOINT_URL` | `http://localhost:4566` | unset → real AWS |
| Credentials | LocalStack dummy keys | IAM role (ECS task role) |
| Region | `us-east-1` | your deploy region |

## Routing and Access Control

All AWS endpoints are under `/api/v1/aws/*` and require a superuser JWT.

Business endpoints (items, users, auth) live under `/api/v1/items`, `/api/v1/users`, `/api/v1/auth` and are not superuser-gated.

## Event Flows

### Flow 1 — File upload to async processing (S3 + SQS + Celery)

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

### Flow 4 — Serverless processing (Lambda)

```
FastAPI ──▶ Lambda.invoke(payload)
              │
              ├── Sync (RequestResponse) ──▶ result returned
              ├── Async (Event) ──▶ background execution
              ├── Version + Alias ──▶ stable prod/staging endpoints
              ├── Event Source Mapping ──▶ SQS/SNS/DynamoDB → Lambda
              └── Layers ──▶ shared dependencies across functions
```

Lambda replaces long-running API tasks with short-lived functions:
- Thumbnail generation from S3 uploads
- Report exports and data transformations
- Event-driven processing from SQS/SNS/DynamoDB
- Scheduled cleanup jobs via CloudWatch Events

### Flow 5 — Observability (CloudWatch + SigNoz)

```
Every request ──▶ structured JSON log ──▶ CloudWatch Logs
                       └── OpenTelemetry traces/metrics/logs ──▶ SigNoz
                             └── Service Map, distributed tracing, exception tracking
```

CloudWatch handles AWS-native metrics and alarms. SigNoz handles application-level observability with OpenTelemetry:
- Traces show request paths across FastAPI, database, Redis, Celery, and AWS services
- Metrics include RED (Rate, Errors, Duration) for every endpoint
- Logs are correlated with traces via trace IDs

### Flow 6 — Flexible hot data (DynamoDB)

```
POST /aws/dynamodb/items ──▶ put_item(pk, sk, data, gsi1pk, gsi1sk)
GET  /aws/dynamodb/items/{pk}/{sk} ──▶ get_item
POST /aws/dynamodb/query ──▶ query_items | query_gsi1 (indexes for alternative access)
```

## Infrastructure Provisioning

All AWS infrastructure is provisioned using **Terraform** (infrastructure as code).

```
infrastructure/terraform/
├── main.tf               # Main resource definitions
├── variables.tf          # Input variables
├── outputs.tf            # Output values
└── modules/              # Reusable modules
    ├── vpc/              # VPC, subnets, security groups
    ├── rds/              # PostgreSQL RDS
    ├── redis/            # ElastiCache Redis
    ├── s3/               # S3 bucket
    ├── dynamodb/         # DynamoDB table
    ├── sqs/              # SQS queue with DLQ
    ├── sns/              # SNS topic
    ├── iam/              # IAM roles and policies
    ├── lambda/           # Lambda function + API Gateway
    ├── ecs/              # ECS cluster, task, service
    ├── alb/              # Application Load Balancer
    ├── cloudwatch/       # Logs, metrics, alarms
    └── signoz/           # SigNoz observability
```

**Deploy:**
```bash
cd infrastructure/terraform
terraform init
terraform plan
terraform apply
```

State is stored in S3 (`fastapi-terraform-state`) with DynamoDB locking (`fastapi-terraform-locks`).

## Production Components

| Component | AWS Service | Provisioning |
|-----------|-------------|--------------|
| FastAPI app | ECS on Fargate | Terraform (`modules/ecs`) |
| PostgreSQL | RDS | Terraform (`modules/rds`) |
| Redis | ElastiCache | Terraform (`modules/redis`) |
| Object storage | S3 | Terraform (`modules/s3`) |
| NoSQL | DynamoDB | Terraform (`modules/dynamodb`) |
| Queues | SQS | Terraform (`modules/sqs`) |
| Notifications | SNS | Terraform (`modules/sns`) |
| Secrets | Secrets Manager | Manual / Terraform |
| Serverless | Lambda + API Gateway | Terraform (`modules/lambda`) + Serverless Framework |
| Monitoring | CloudWatch + SigNoz | Terraform (`modules/cloudwatch`, `modules/signoz`) |
| Load balancer | ALB | Terraform (`modules/alb`) |
| AWS access | IAM roles | Terraform (`modules/iam`) |

## Cost Notes

- **S3** — ~$0.023/GB/month; use lifecycle rules to archive/expire old objects.
- **DynamoDB** — on-demand (PAY_PER_REQUEST) avoids idle costs; GSIs double write cost.
- **SQS** — long polling minimizes API calls; messages <= 256 KB.
- **SNS** — free per topic (pay per message + per subscriber endpoint).
- **Secrets Manager** — $0.40/secret/month + rotation cost; cache reads.
- **Lambda** — pay per GB-second; keep functions short and small memory (128–512 MB typical).
- **CloudWatch** — metrics are cheap; logs/retention and custom metrics are where cost grows.

## Security Summary

| Layer | Control |
|-------|---------|
| Network | VPC + private subnets; ALB in public; services in private via VPC endpoints |
| IAM | One role per workload, least-privilege policies (see per-service guides) |
| Secrets | Secrets Manager with KMS + rotation; no secrets in images/repo |
| App | JWT auth; superuser gate on /aws/*; input validation via Pydantic |
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
- [SigNoz Guide](signoz-guide.md) — OpenTelemetry observability with traces, metrics, logs, APM
- [Terraform Guide](terraform-guide.md) — infrastructure as code with Terraform
- [Serverless Guide](serverless-guide.md) — Lambda + API Gateway with Serverless Framework

← Back to [Docs Index](README.md)
