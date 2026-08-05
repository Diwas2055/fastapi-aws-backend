# Terraform Guide

## What It Is

Terraform is infrastructure as code (IaC) tool. You write code to define your AWS infrastructure, and Terraform creates and manages those resources for you. Instead of manually clicking in AWS Console, you have version-controlled, repeatable infrastructure.

## Why We Use It

This FastAPI backend needs reliable, repeatable infrastructure:
- Same setup in dev, staging, and production
- Track every infrastructure change in git
- Roll back infrastructure changes like code changes
- Multiple team members can safely provision resources
- Audit trail of who changed what and when

## Architecture

```
Terraform State (S3) ──▶ Terraform ──▶ AWS Resources
                              │
                              ├── VPC (networking)
                              ├── RDS (database)
                              ├── ElastiCache (Redis)
                              ├── S3 (storage)
                              ├── DynamoDB (NoSQL)
                              ├── SQS (queues)
                              ├── SNS (notifications)
                              ├── Lambda (serverless)
                              ├── ECS + ALB (FastAPI app)
                              ├── CloudWatch (monitoring)
                              └── SigNoz (observability)
```

## Directory Structure

```
infrastructure/terraform/
├── providers.tf          # AWS provider and backend config
├── variables.tf          # Input variables
├── main.tf               # Main resource definitions
├── outputs.tf            # Output values
├── terraform.tfvars.example  # Example variable values
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

## Setup

### Prerequisites

```bash
# Install Terraform
brew install terraform  # macOS
# or download from https://developer.hashicorp.com/terraform/downloads

# Verify installation
terraform version
```

### Configuration

1. **Copy example variables:**
```bash
cp infrastructure/terraform/terraform.tfvars.example infrastructure/terraform/terraform.tfvars
```

2. **Edit `terraform.tfvars` with your values:**
```hcl
aws_region = "us-east-1"
environment = "dev"
db_password = "your-secure-password"
container_image = "your-ecr-image:latest"
```

3. **Create S3 bucket for Terraform state:**
```bash
aws s3 mb s3://fastapi-terraform-state --region us-east-1
aws s3api put-bucket-versioning --bucket fastapi-terraform-state --versioning-configuration Status=Enabled
```

4. **Create DynamoDB table for state locking:**
```bash
aws dynamodb create-table \
  --table-name fastapi-terraform-locks \
  --attribute-definitions AttributeName=LockID,AttributeType=S \
  --key-schema AttributeName=LockID,KeyType=HASH \
  --billing-mode PAY_PER_REQUEST \
  --region us-east-1
```

### Commands

```bash
# Navigate to Terraform directory
cd infrastructure/terraform

# Initialize Terraform
terraform init

# Preview changes
terraform plan

# Apply changes
terraform apply

# Destroy infrastructure
terraform destroy

# View outputs
terraform output
```

## Resources Created

### Networking
- VPC with public, private, and data subnets across 3 AZs
- Internet Gateway and NAT Gateways
- Security groups for ALB, ECS, RDS, Redis, Lambda, SigNoz

### Database
- RDS PostgreSQL 16 with encryption and Multi-AZ in production
- Automated backups and CloudWatch monitoring
- DB parameter group and option group

### Cache
- ElastiCache Redis 7.1 with encryption in transit and at rest
- Auth token for non-development environments
- CloudWatch slow log delivery

### Storage
- S3 bucket with versioning (production only)
- SSE-KMS encryption
- Public access block
- Lifecycle rules (IA after 30 days, Glacier after 90 days, expiry after 365 days)

### NoSQL
- DynamoDB table with PAY_PER_REQUEST billing
- GSI1 for alternative access patterns
- Point-in-time recovery (production)
- Streams enabled

### Queues
- SQS queue with long polling (20s)
- Dead Letter Queue (DLQ) with max receive count of 3
- SNS subscription to queue

### Notifications
- SNS topic with SQS subscription
- Fan-out architecture support

### IAM
- ECS task execution role
- ECS task role with least-privilege S3/DynamoDB/SQS/SNS/CloudWatch permissions
- Lambda execution role with VPC access
- Custom IAM policy for application services

### Lambda
- Lambda function with Python 3.12 runtime
- VPC access (private subnets)
- API Gateway HTTP API
- CloudWatch logs
- Environment variables for all AWS services

### ECS
- Fargate cluster with container insights (production)
- Task definition with health checks
- Service with deployment circuit breaker
- Auto scaling (production: 2-10 tasks, CPU target 70%)

### Load Balancer
- Application Load Balancer (ALB)
- HTTP listener on port 80
- HTTPS listener on port 443 (if certificate provided)
- HTTP to HTTPS redirect (if certificate provided)
- Target group with health checks on /health

### CloudWatch
- Log groups with configurable retention
- Alarms:
  - ECS CPU > 80%
  - ECS Memory > 80%
  - ALB response time > 2s
  - RDS CPU > 80%
  - Unhealthy hosts

### SigNoz (Optional)
- EC2 instance in private subnet
- Security group allowing ports 3301, 4317, 4318

## Outputs

After `terraform apply`, you get:

| Output | Description |
|--------|-------------|
| `vpc_id` | VPC ID |
| `public_subnet_ids` | Public subnet IDs |
| `private_subnet_ids` | Private subnet IDs |
| `alb_dns_name` | ALB DNS name |
| `alb_zone_id` | ALB zone ID for Route53 alias |
| `rds_endpoint` | RDS endpoint (host:port) |
| `redis_endpoint` | Redis endpoint |
| `s3_bucket_name` | S3 bucket name |
| `dynamodb_table_name` | DynamoDB table name |
| `sqs_queue_url` | SQS queue URL |
| `sns_topic_arn` | SNS topic ARN |
| `lambda_function_arn` | Lambda function ARN |
| `lambda_function_name` | Lambda function name |
| `api_gateway_url` | API Gateway URL |
| `ecs_cluster_name` | ECS cluster name |
| `ecs_service_name` | ECS service name |
| `cloudwatch_log_group_name` | CloudWatch log group name |
| `signoz_ui_url` | SigNoz UI URL (if deployed) |

## Environment Variables

After Terraform creates resources, configure these in your FastAPI app:

```bash
# From Terraform outputs
DATABASE_URL=postgresql+asyncpg://${db_username}:${db_password}@${rds_endpoint}/${db_name}
REDIS_URL=redis://${redis_endpoint}:6379/0
S3_BUCKET=${s3_bucket_name}
DYNAMODB_TABLE=${dynamodb_table_name}
SQS_QUEUE_URL=${sqs_queue_url}
SNS_TOPIC_ARN=${sns_topic_arn}
LAMBDA_FUNCTION_NAME=${lambda_function_name}
CLOUDWATCH_LOG_GROUP=${cloudwatch_log_group_name}
AWS_REGION=${aws_region}
```

## Workspaces

Use Terraform workspaces for multiple environments:

```bash
# Create workspace
terraform workspace new dev
terraform workspace new staging
terraform workspace new production

# Switch workspace
terraform workspace select dev

# List workspaces
terraform workspace list
```

## State Management

Terraform state is stored in S3 with DynamoDB locking:

```hcl
# In providers.tf
terraform {
  backend "s3" {
    bucket         = "fastapi-terraform-state"
    key            = "terraform/terraform.tfstate"
    region         = "us-east-1"
    encrypt        = true
    dynamodb_table = "fastapi-terraform-locks"
  }
}
```

## Best Practices

1. **Never edit Terraform state manually** — use `terraform apply` and `terraform destroy`
2. **Always run `terraform plan` before `terraform apply`** — review changes
3. **Use workspaces or separate state files** for dev/staging/production
4. **Enable state locking** with DynamoDB (already configured)
5. **Enable versioning** on the state bucket (already configured)
6. **Encrypt state at rest** — already enabled with S3 SSE
7. **Use modules** for reusable components (already done)
8. **Tag all resources** — already configured with default tags
9. **Use remote state data sources** to share outputs between workspaces
10. **Keep sensitive data out of state** — use `sensitive = true` for passwords

## Common Commands

```bash
# Initialize
terraform init

# Format code
terraform fmt -recursive

# Validate configuration
terraform validate

# Plan changes
terraform plan -out=tfplan

# Apply plan
terraform apply tfplan

# Destroy resources
terraform destroy

# Import existing resource
terraform import module.rds.aws_db_instance.main <instance-id>

# Refresh state
terraform refresh

# Show current state
terraform show

# List resources
terraform state list

# Remove resource from state (not destroy)
terraform state rm <address>
```

## CI/CD Integration

Add to `.github/workflows/`:

```yaml
- name: Terraform Plan
  run: |
    cd infrastructure/terraform
    terraform init
    terraform plan -no-color

- name: Terraform Apply
  if: github.ref == 'refs/heads/main'
  run: |
    cd infrastructure/terraform
    terraform apply -auto-approve
```

## Troubleshooting

| Issue | Cause | Fix |
|-------|-------|-----|
| `state lock` | Another process is running | Wait or `terraform force-unlock` |
| `resource already exists` | Resource created outside Terraform | Import with `terraform import` |
| `dependency cycle` | Circular dependency in modules | Review module dependencies |
| `backend changed` | Backend config modified | `terraform init -reconfigure` |

---

← Back to [Docs Index](README.md)
