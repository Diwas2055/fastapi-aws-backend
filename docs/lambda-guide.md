# Lambda — Enterprise Serverless Functions

## What It Is

AWS Lambda runs your code in response to events without managing servers. You pay only for the compute time while your code runs (billed in 1ms increments). Lambdas are triggered by API Gateway, S3 events, SNS/SQS messages, DynamoDB Streams, or scheduled CloudWatch Events.

This project implements Lambda as an enterprise-grade serverless layer with full lifecycle management, versioning, aliases, event source mappings, layers, code signing, concurrency control, and retry patterns.

## Why We Use It

In this FastAPI backend, Lambda handles:

- **Offloaded processing** — image thumbnails, report exports, data enrichment off the API path
- **Event-driven reactions** — S3 upload → Lambda thumbnail, SNS publish → Lambda handler
- **Scheduled jobs** — cleanup, reminders, batch processing via CloudWatch Events
- **Async workflows** — fire-and-forget tasks that don't need immediate response
- **Integration bridges** — connect AWS services without managing servers

## Architecture

```
FastAPI App
    │
    ├── invoke (sync) ──▶ Lambda ──▶ result returned to caller
    ├── invoke_async ──▶ Lambda ──▶ runs in background
    ├── create/update/delete ──▶ Lambda lifecycle management
    ├── publish_version ──▶ immutable versions
    ├── create_alias ──▶ stable endpoints (prod, staging)
    └── create_event_source_mapping ──▶ SQS/SNS/DynamoDB streams → Lambda
```

## Enterprise Features

### Function Lifecycle

| Operation | Method | Description |
|-----------|--------|-------------|
| Create | `POST /lambda/functions` | Create function with full config |
| Get | `GET /lambda/functions/{name}` | Get function configuration |
| List | `GET /lambda/functions` | List all functions |
| Update code | `POST /lambda/functions/{name}/code` | Update from inline code |
| Update config | `PUT /lambda/functions/{name}` | Update timeout, memory, env vars |
| Delete | `DELETE /lambda/functions/{name}` | Delete function |

### Versioning

| Operation | Method | Description |
|-----------|--------|-------------|
| Publish | `POST /lambda/functions/{name}/versions` | Publish immutable version |
| List | `GET /lambda/functions/{name}/versions` | List all versions |

### Aliases

| Operation | Method | Description |
|-----------|--------|-------------|
| Create | `POST /lambda/functions/{name}/aliases` | Create alias (prod, staging) |
| List | `GET /lambda/functions/{name}/aliases` | List aliases |
| Delete | `DELETE /lambda/functions/{name}/aliases/{alias}` | Delete alias |

### Event Source Mappings

| Operation | Method | Description |
|-----------|--------|-------------|
| Create | `POST /lambda/functions/{name}/event-source-mappings` | Connect SQS/SNS/DynamoDB |
| List | `GET /lambda/functions/{name}/event-source-mappings` | List mappings |
| Delete | `DELETE /lambda/event-source-mappings/{uuid}` | Remove mapping |

### Layers

| Operation | Method | Description |
|-----------|--------|-------------|
| Publish | `POST /lambda/layers` | Publish a layer |
| List | `GET /lambda/layers` | List layers |

### Concurrency

| Operation | Method | Description |
|-----------|--------|-------------|
| Set | `POST /lambda/functions/{name}/concurrency` | Set reserved concurrency |
| Delete | `DELETE /lambda/functions/{name}/concurrency` | Remove limit |

### Permissions

| Operation | Method | Description |
|-----------|--------|-------------|
| Add | `POST /lambda/functions/{name}/permissions` | Add resource policy |
| Remove | `DELETE /lambda/functions/{name}/permissions/{id}` | Remove policy |
| Get | `GET /lambda/functions/{name}/policy` | Get current policy |

### Invocation

| Operation | Method | Description |
|-----------|--------|-------------|
| Invoke | `POST /lambda/invoke` | Sync or async invocation |
| Invoke + retry | `POST /lambda/invoke-with-retry` | With exponential backoff |

## Configuration

### Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `LAMBDA_FUNCTION_NAME` | `None` | Default function to invoke |
| `AWS_ENDPOINT_URL` | `http://localhost:4566` | LocalStack endpoint |
| `AWS_REGION` | `us-east-1` | AWS region |

### Service Class

```python
# app/services/aws/lambda_service.py
class LambdaService:
    # Function CRUD
    async def create_function(config: LambdaFunctionConfig) -> dict | None
    async def get_function(name, qualifier=None) -> dict | None
    async def list_functions(max_items=50) -> dict
    async def update_function_code(name, zip_file=None, s3_bucket=None, s3_key=None, publish=False) -> dict | None
    async def update_function_configuration(name, **kwargs) -> dict | None
    async def delete_function(name, qualifier=None) -> bool

    # Versions
    async def publish_version(name, description=None) -> dict | None
    async def list_versions_by_function(name, max_items=50) -> dict

    # Aliases
    async def create_alias(name, alias_name, version="$LATEST") -> dict | None
    async def update_alias(name, alias_name, version=None) -> dict | None
    async def delete_alias(name, alias_name) -> bool
    async def list_aliases(name, max_items=50) -> dict

    # Invocation
    async def invoke(payload, name=None, invocation_type="RequestResponse", qualifier=None) -> dict | None
    async def invoke_async(payload, name=None, qualifier=None) -> dict | None
    async def invoke_with_retry(payload, name=None, max_retries=3) -> dict | None

    # Event Source Mappings
    async def create_event_source_mapping(event_source_arn, function_name, ...) -> dict | None
    async def list_event_source_mappings(function_name=None, event_source_arn=None) -> dict
    async def delete_event_source_mapping(uuid) -> bool
    async def get_event_source_mapping(uuid) -> dict | None

    # Layers
    async def publish_layer_version(name, content, ...) -> dict | None
    async def list_layers(max_items=50) -> dict
    async def get_layer_version(name, version) -> dict | None

    # Tags
    async def tag_resource(arn, tags) -> bool
    async def untag_resource(arn, keys) -> bool

    # Permissions
    async def add_permission(name, statement_id, action, principal, ...) -> dict | None
    async def remove_permission(name, statement_id, qualifier=None) -> bool
    async def get_policy(name, qualifier=None) -> dict | None

    # Concurrency
    async def put_function_concurrency(name, reserved) -> dict | None
    async def delete_function_concurrency(name) -> bool
```

Uses aioboto3 with `lambda_service = LambdaService()` global instance.

## Code Usage Examples

### 1. Create a function from inline code

```python
from app.services.aws import lambda_service

result = await lambda_service.create_function(
    function_name="thumbnail-generator",
    runtime="python3.12",
    role="arn:aws:iam::000000000000:role/lambda-ex",
    handler="lambda_function.handler",
    code="""
import boto3
def handler(event, context):
    bucket = event['bucket']
    key = event['key']
    s3 = boto3.client('s3')
    # generate thumbnail...
    return {'statusCode': 200, 'body': 'ok'}
""",
    timeout=30,
    memory_size=256,
    environment={"S3_BUCKET": "fastapi-uploads"},
    tags={"team": "media", "env": "dev"},
)
# result -> {FunctionName, FunctionArn, Runtime, Timeout, State, ...}
```

### 2. Invoke synchronously (wait for result)

```python
result = await lambda_service.invoke(
    function_name="thumbnail-generator",
    payload={"bucket": "fastapi-uploads", "key": "image.jpg"},
    invocation_type="RequestResponse",
)
# -> {
#   "status_code": 200,
#   "payload": {"statusCode": 200, "body": "ok"},
#   "log_result": "...",
#   "function_error": None,
#   "executed_version": "1"
# }
```

### 3. Invoke asynchronously (fire-and-forget)

```python
result = await lambda_service.invoke_async(
    function_name="report-exporter",
    payload={"user_id": "123", "format": "pdf"},
)
# result -> {"status_code": 202, ...}
# API returns immediately; Lambda runs in background
```

### 4. Invoke with retry

```python
result = await lambda_service.invoke_with_retry(
    payload={"data": "value"},
    function_name="unreliable-processor",
    max_retries=3,
)
# Retries up to 3 times with exponential backoff on failure
```

### 5. Versioning and aliases

```python
# Publish a new version
version = await lambda_service.publish_version("thumbnail-generator", description="v2 with better quality")

# Create prod alias pointing to this version
await lambda_service.create_alias(
    function_name="thumbnail-generator",
    name="prod",
    function_version=version["Version"],
)

# Update alias to new version
await lambda_service.update_alias(
    function_name="thumbnail-generator",
    name="prod",
    function_version="5",
)

# Invoke via stable alias
await lambda_service.invoke(payload={...}, function_name="thumbnail-generator", qualifier="prod")
```

### 6. Event source mapping (SQS → Lambda)

```python
await lambda_service.create_event_source_mapping(
    event_source_arn="arn:aws:sqs:us-east-1:123456789012:my-queue",
    function_name="queue-processor",
    starting_position="LATEST",
    batch_size=10,
    maximum_batching_window_in_seconds=5,
    enabled=True,
)
```

### 7. Layers

```python
# Publish a layer
zip_bytes = lambda_service._build_layer_zip(python_libs=["requests", "pandas"])
await lambda_service.publish_layer_version(
    layer_name="my-data-layer",
    content=zip_bytes,
    compatible_runtimes=["python3.12"],
)

# Attach layer to function
await lambda_service.update_function_configuration(
    function_name="my-function",
    layers=["arn:aws:lambda:us-east-1:123456789012:layer:my-data-layer:1"],
)
```

### 8. Concurrency control

```python
# Reserve 10 concurrent executions
await lambda_service.put_function_concurrency("expensive-function", reserved_concurrent_executions=10)

# Remove limit
await lambda_service.delete_function_concurrency("expensive-function")
```

## API Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| `POST` | `/api/v1/aws/lambda/invoke` | Invoke function |
| `POST` | `/api/v1/aws/lambda/invoke-with-retry` | Invoke with retry |
| `POST` | `/api/v1/aws/lambda/functions` | Create function |
| `GET` | `/api/v1/aws/lambda/functions` | List functions |
| `GET` | `/api/v1/aws/lambda/functions/{name}` | Get function |
| `PUT` | `/api/v1/aws/lambda/functions/{name}` | Update function config |
| `DELETE` | `/api/v1/aws/lambda/functions/{name}` | Delete function |
| `POST` | `/api/v1/aws/lambda/functions/{name}/code` | Update code |
| `POST` | `/api/v1/aws/lambda/functions/{name}/versions` | Publish version |
| `GET` | `/api/v1/aws/lambda/functions/{name}/versions` | List versions |
| `POST` | `/api/v1/aws/lambda/functions/{name}/aliases` | Create alias |
| `GET` | `/api/v1/aws/lambda/functions/{name}/aliases` | List aliases |
| `DELETE` | `/api/v1/aws/lambda/functions/{name}/aliases/{alias}` | Delete alias |
| `POST` | `/api/v1/aws/lambda/functions/{name}/event-source-mappings` | Create mapping |
| `GET` | `/api/v1/aws/lambda/functions/{name}/event-source-mappings` | List mappings |
| `DELETE` | `/api/v1/aws/lambda/event-source-mappings/{uuid}` | Delete mapping |
| `POST` | `/api/v1/aws/lambda/layers` | Publish layer |
| `GET` | `/api/v1/aws/lambda/layers` | List layers |
| `POST` | `/api/v1/aws/lambda/functions/{name}/concurrency` | Set concurrency |
| `DELETE` | `/api/v1/aws/lambda/functions/{name}/concurrency` | Remove concurrency |
| `POST` | `/api/v1/aws/lambda/functions/{name}/permissions` | Add permission |
| `DELETE` | `/api/v1/aws/lambda/functions/{name}/permissions/{id}` | Remove permission |
| `GET` | `/api/v1/aws/lambda/functions/{name}/policy` | Get policy |

## LocalStack Setup

### Prerequisites

LocalStack requires Docker access for Lambda execution. The default `localstack/localstack:3.6` image includes the Lambda executor.

### IAM Role

```bash
# Create a dummy IAM role for Lambda execution
aws --endpoint-url=http://localhost:4566 iam create-role \
    --role-name lambda-ex \
    --assume-role-policy-document '{
        "Version":"2012-10-17",
        "Statement":[{
            "Effect":"Allow",
            "Principal":{"Service":"lambda.amazonaws.com"},
            "Action":"sts:AssumeRole"
        }]
    }' \
    --region us-east-1
```

### Create a Function via CLI

```bash
# Create function from local zip
mkdir -p /tmp/lambda && cd /tmp/lambda
cat > lambda_function.py <<'EOF'
def handler(event, context):
    print("got event:", event)
    return {"statusCode": 200, "body": "hello from lambda"}
EOF
zip -r fn.zip lambda_function.py

aws --endpoint-url=http://localhost:4566 lambda create-function \
    --function-name fastapi-aws-backend-lambda \
    --runtime python3.12 \
    --handler lambda_function.handler \
    --role arn:aws:iam::000000000000:role/lambda-ex \
    --zip-file fileb://fn.zip \
    --region us-east-1

# Invoke (sync)
aws --endpoint-url=http://localhost:4566 lambda invoke \
    --function-name fastapi-aws-backend-lambda \
    --payload '{"hello":"world"}' \
    --cli-binary-format raw-in-base64-out \
    out.json --region us-east-1 && cat out.json
```

### Via This API

```bash
# Create function via API
curl -X POST http://localhost:8000/api/v1/aws/lambda/functions \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "function_name": "my-function",
    "runtime": "python3.12",
    "handler": "lambda_function.handler",
    "code": "def handler(event, context):\n    return {\"statusCode\": 200, \"body\": \"ok\"}\n",
    "timeout": 30,
    "memory_size": 128
  }'

# Invoke
curl -X POST http://localhost:8000/api/v1/aws/lambda/invoke \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "function_name": "my-function",
    "payload": {"hello": "world"}
  }'
```

### Auto-initialization

On app startup in non-production environments, the app automatically creates a sample Lambda function (`fastapi-aws-backend-lambda`) with a simple handler. See `app/services/aws_init_service.py`.

## Production Configuration

### IAM Policy

```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Action": [
        "lambda:InvokeFunction",
        "lambda:InvokeAsync",
        "lambda:ListFunctions",
        "lambda:GetFunction",
        "lambda:GetFunctionConfiguration",
        "lambda:CreateFunction",
        "lambda:UpdateFunctionCode",
        "lambda:UpdateFunctionConfiguration",
        "lambda:DeleteFunction",
        "lambda:PublishVersion",
        "lambda:ListVersionsByFunction",
        "lambda:CreateAlias",
        "lambda:UpdateAlias",
        "lambda:DeleteAlias",
        "lambda:ListAliases",
        "lambda:CreateEventSourceMapping",
        "lambda:ListEventSourceMappings",
        "lambda:DeleteEventSourceMapping",
        "lambda:PublishLayerVersion",
        "lambda:ListLayers",
        "lambda:GetLayerVersion",
        "lambda:AddPermission",
        "lambda:RemovePermission",
        "lambda:GetPolicy",
        "lambda:PutFunctionConcurrency",
        "lambda:DeleteFunctionConcurrency"
      ],
      "Resource": "arn:aws:lambda:us-east-1:123456789012:function:*"
    }
  ]
}
```

### Environment Variables

```bash
# .env.production
LAMBDA_FUNCTION_NAME=my-prod-function
AWS_REGION=us-east-1
```

### Best Practices

1. **Prefer async (Event) invocation** for fire-and-forget work to keep API latency low.
2. **Keep payloads small** — request payload limit is 6 MB (sync) / 256 KB (async).
3. **Set timeouts and memory** — match function timeout to expected duration; over-allocating memory costs more.
4. **Make functions idempotent** — events can be retried or delivered twice.
5. **Use aliases/versions** — deploy to `$LATEST`, promote to prod alias; app invokes the stable alias.
6. **Use reserved concurrency** — protect downstream resources from Lambda overload.
7. **Enable DLQs** — configure dead letter queues for async invocations.
8. **Use layers** — share common dependencies across functions.
9. **CloudWatch for logging** — Lambda auto-logs to CloudWatch; keep structured logging in handler.
10. **IAM least privilege** — give each Lambda only the permissions it needs.
11. **VPC and security groups** — run Lambda in VPC for private resource access.
12. **Provisioned concurrency** — for latency-sensitive paths, eliminates cold starts.

### LocalStack vs Production

| Feature | LocalStack | Production |
|---------|-----------|------------|
| IAM role | Dummy ARN (`arn:aws:iam::000000000000:role/...`) | Real IAM role ARN |
| Code upload | Inline ZIP or S3 | S3 or ECR image |
| Execution | Docker container | AWS managed infrastructure |
| Concurrency | Limited by Docker | Scales automatically |
| Logs | Container logs | CloudWatch Logs |
| Tracing | SigNoz / OpenTelemetry | X-Ray + SigNoz |

## Common Errors

| Error | Cause | Fix |
|-------|-------|-----|
| `ResourceNotFoundException` | Function name wrong / region mismatch | Verify function name |
| `AccessDeniedException` | IAM lacks `lambda:InvokeFunction` | Update IAM policy |
| `RequestEntityTooLargeException` | Payload > 256 KB (async) | Use sync (6 MB) or S3 reference |
| `FunctionError` | Lambda handler raised | Inspect logs |
| `TooManyRequestsException` | Concurrency limit hit | Raise reserved concurrency / retry |
| `EC2ThrottledException` | Cold-start subnet issues | Check VPC config / warm pools |
| `InvalidParameterValueException` | Timeout/memory out of range | Timeout max 900s, memory 128-10240 MB |
| `ResourceConflictException` | Function already exists | Use update instead of create |

## Monitoring

Lambda metrics available in SigNoz / CloudWatch:

- `Duration` — execution time
- `Errors` — failed invocations
- `Throttles` — concurrency limit hits
- `IteratorAge` — event source mapping lag
- `ConcurrentExecutions` — current concurrency

---

← Back to [Docs Index](README.md) · Next: [CloudWatch Guide](cloudwatch-guide.md)
