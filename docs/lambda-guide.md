# Lambda — Serverless Function Invocation

## What It Is

AWS Lambda runs your code in response to events without you managing servers. You pay only for the compute time while your code runs (billed in 100ms increments). Lambdas are triggered by API Gateway, S3 events, SNS/SQS messages, DynamoDB Streams, or scheduled CloudWatch Events.

## Why We Use It

In this FastAPI backend, Lambda is the serverless reaction layer:
- Run short functions from the API (image thumbnails, report exports, data enrichment)
- Move expensive work off the API process so requests stay fast
- Event-driven patterns: S3 upload → Lambda thumbnail, SNS publish → Lambda handler, scheduled cleanup

## How It Works

### Architecture

```
┌──────────┐   POST /lambda/invoke   ┌──────────────┐   InvocationType=Event  ┌─────────────────┐
│ FastAPI  │ ──────────────────────▶ │ LambdaService│ ──────────────────────▶ │  Lambda function │
│   app    │                         │  (boto3)     │                          │  (serverless)    │
└──────────┘                         └──────────────┘                          └─────────────────┘
```

Two invocation modes:
- **Event (async, fire-and-forget)**: `invocation_type="Event"` — API returns immediately; Lambda runs in background. `invoke_async()` wraps this and returns `True` on HTTP 202.
- **RequestResponse (sync, default)**: `invocation_type="RequestResponse"` — API waits for Lambda result.

### Configuration

```python
# app/core/config.py
LAMBDA_FUNCTION_NAME: Optional[str] = None   # default function to invoke
```

| Config | Default | Purpose |
|--------|---------|---------|
| `LAMBDA_FUNCTION_NAME` | `None` | Function to invoke when none specified |

### Service Class

```python
# app/services/aws/lambda_service.py
class LambdaService:
    async def invoke(payload: dict, function_name=None, invocation_type="RequestResponse", log_type="Tail") -> dict | None
    async def invoke_async(payload: dict, function_name=None) -> bool          # Event wrapper (202)
    async def create_function(function_name, runtime, role, handler, code, description=None, timeout=30, memory_size=128, environment=None) -> str | None
    async def update_function_code(function_name, zip_file: bytes) -> bool
    async def update_function_configuration(function_name, **kwargs) -> bool
    async def delete_function(function_name) -> bool
    async def get_function(function_name) -> dict | None                       # Configuration
```

Uses aioboto3 with `lambda_service = LambdaService()` global instance.

## Code Usage Examples

### 1. Async (fire-and-forget) invocation

```python
from app.services.aws import lambda_service

ok = await lambda_service.invoke_async(
    function_name="thumbnail-generator",
    payload={"bucket": "fastapi-uploads", "key": "images/large.jpg", "sizes": [128, 256, 512]},
)
# ok == True  → Lambda accepted (HTTP 202); API returns immediately
```

### 2. Sync invocation (wait for result)

```python
result = await lambda_service.invoke(
    function_name="sentiment-analyzer",
    payload={"text": "I love this product!"},
    invocation_type="RequestResponse",
)
# -> {"status_code": 200, "payload": {"sentiment": "positive", "score": 0.95},
#     "log_result": "...", "function_error": None}
```

### 3. Manage a function (create / update / delete)

```python
arn = await lambda_service.create_function(
    function_name="thumbnail-generator",
    runtime="python3.12",
    role="arn:aws:iam::000000000000:role/lambda-ex",
    handler="lambda_function.handler",
    code={"ZipFile": zip_bytes},          # deployment package
    timeout=30,
    memory_size=128,
    environment={"S3_BUCKET": "fastapi-uploads"},
)

await lambda_service.update_function_code("thumbnail-generator", new_zip_bytes)
await lambda_service.update_function_configuration("thumbnail-generator", Timeout=60, MemorySize=256)

config = await lambda_service.get_function("thumbnail-generator")
# -> {FunctionName, Runtime, MemorySize, Timeout, State, ...}

await lambda_service.delete_function("thumbnail-generator")
```

## API Endpoints

| Method | Endpoint | Auth | Description |
|--------|----------|------|-------------|
| `POST` | `/api/v1/aws/lambda/invoke` | Superuser | Invoke function (body: `function_name`, `payload`, `invocation_type?` default `RequestResponse`) |

## LocalStack Setup

Lambdas need a runner in LocalStack; `LAMBDA_EXECUTOR` defaults to Docker. Simple local function:

```bash
# Create a role (LocalStack accepts a dummy ARN)
aws --endpoint-url=http://localhost:4566 iam create-role \
    --role-name lambda-ex \
    --assume-role-policy-document '{"Version":"2012-10-17","Statement":[{"Effect":"Allow","Principal":{"Service":"lambda.amazonaws.com"},"Action":"sts:AssumeRole"}]}' \
    --region us-east-1

# Create a function from a small zip
mkdir -p /tmp/lambda && cd /tmp/lambda
cat > lambda_function.py <<'EOF'
def handler(event, context):
    print("got event:", event)
    return {"statusCode": 200, "body": "hello from lambda"}
EOF
zip -r fn.zip lambda_function.py

aws --endpoint-url=http://localhost:4566 lambda create-function \
    --function-name fastapi-aws-backend-lambda \
    --runtime python3.12 --handler lambda_function.handler \
    --role arn:aws:iam::000000000000:role/lambda-ex \
    --zip-file fileb://fn.zip --region us-east-1

# Invoke (sync)
aws --endpoint-url=http://localhost:4566 lambda invoke \
    --function-name fastapi-aws-backend-lambda \
    --payload '{"hello":"world"}' --cli-binary-format raw-in-base64-out \
    out.json --region us-east-1 && cat out.json
```

## IAM Policy (production)

```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Action": [
        "lambda:InvokeFunction",
        "lambda:ListFunctions",
        "lambda:GetFunctionConfiguration"
      ],
      "Resource": "arn:aws:lambda:us-east-1:123456789012:function:*"
    }
  ]
}
```

## Best Practices

1. **Prefer async (Event) invocation** for fire-and-forget work — keeps API latency low.
2. **Keep payloads small** — request payload limit is 6 MB (sync) / 256 KB (async).
3. **Set timeouts and memory** — match function timeout to expected duration; over-allocating memory costs more.
4. **Make functions idempotent** — events can be retried or delivered twice (SQS/SNS sources).
5. **Use aliases/versions** — deploy to `$LATEST`, promote to prod alias; app invokes the stable alias.
6. **CloudWatch for logging** — Lambda auto-logs to CloudWatch; keep print/logger in handler.
7. **IAM least privilege** — give each Lambda only the permissions it needs (S3 read for thumbnails, etc.).
8. **Concurrency and DLQs** — set reserved concurrency; use DLQs for async event sources to catch failures.
9. **Warm-up for latency-sensitive paths** — provisioned concurrency removes cold starts for sync calls.

## Common Errors

| Error | Cause | Fix |
|-------|-------|-----|
| `ResourceNotFoundException` | Function name wrong / region mismatch | Verify `LAMBDA_FUNCTION_NAME` |
| `AccessDeniedException` | IAM lacks `lambda:InvokeFunction` | Update IAM policy |
| `RequestEntityTooLargeException` | Payload > 256 KB (async) | Use sync (6 MB) or S3 reference |
| `FunctionError` (in response) | Lambda handler raised | Inspect CloudWatch logs |
| `ServiceException` / throttling | Concurrency limit hit | Raise reserved concurrency / retry with backoff |
| `EC2ThrottledException` | Cold-start subnet issues | Check VPC config / use warm pools |

---

← Back to [Docs Index](README.md) · Next: [CloudWatch Guide](cloudwatch-guide.md)
