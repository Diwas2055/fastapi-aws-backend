# DynamoDB — NoSQL Database with GSI Support

## What It Is

Amazon DynamoDB is AWS's fully managed, serverless NoSQL key-value and document database. It delivers single-digit-millisecond performance at any scale, with automatic scaling, replication across three AZs, and on-demand capacity.

## Why We Use It

In this FastAPI backend, DynamoDB serves as the high-throughput, low-latency data layer for workloads that don't need SQL relations:
- Storing flexible, schema-less JSON documents (`data` field)
- High-read/low-write access patterns (counters, session data, feature toggles, analytics events)
- Complementing PostgreSQL: relational data stays in Postgres, hot/flexible data goes to DynamoDB

## Data Model — Single Table Design with GSI

The app uses the recommended single-table design with a composite `pk`/`sk` key and one **Global Secondary Index (GSI1)** for alternative query patterns.

### Table Structure

| Attribute | Type | Key | Purpose |
|-----------|------|-----|---------|
| `pk` | String | Partition Key (HASH) | Primary access path (e.g., `USER#123`) |
| `sk` | String | Sort Key (RANGE) | Ordering / grouping (e.g., `ITEM#456`) |
| `gsi1pk` | String | GSI1 HASH | Alternate query path (e.g., `CATEGORY#electronics`) |
| `gsi1sk` | String | GSI1 RANGE | GSI ordering |
| `data` | Map | — | Flexible JSON payload |
| `created_at` / `updated_at` | String | — | Timestamps (ISO-8601) |

### Example Items

```
USER#123 | ITEM#456 | {name: "Laptop", price: 999} | CATEGORY#electronics | PRICE#999
USER#123 | ITEM#789 | {name: "Mouse",  price: 49}  | CATEGORY#electronics | PRICE#49
USER#999 | ITEM#111 | {name: "Chair",  price: 299} | CATEGORY#furniture    | PRICE#299
```

- **Query 1**: "All items for user 123" → `query(pk=USER#123, sk_prefix=ITEM#)`
- **Query 2**: "All electronics sorted by price" → `query_gsi1(gsi1pk=CATEGORY#electronics)`

## How It Works

### Configuration

```python
# app/core/config.py
DYNAMODB_TABLE: str = "fastapi-items"
DYNAMODB_ENDPOINT_URL: Optional[str] = None  # falls back to AWS_ENDPOINT_URL (LocalStack)
```

| Config | Default | Purpose |
|--------|---------|---------|
| `DYNAMODB_TABLE` | `fastapi-items` | Table name |
| `DYNAMODB_ENDPOINT_URL` | `None` | Override endpoint (falls back to `AWS_ENDPOINT_URL`) |

### Service Class

```python
# app/services/aws/dynamodb_service.py
class DynamoDBService:
    async def create_table() -> bool
    async def put_item(pk, sk, data, gsi1pk=None, gsi1sk=None) -> bool
    async def get_item(pk, sk) -> dict | None
    async def update_item(pk, sk, data) -> bool
    async def delete_item(pk, sk) -> bool
    async def query_items(pk, sk_prefix=None, limit=100, last_evaluated_key=None) -> dict
    async def query_gsi1(gsi1pk, gsi1sk_prefix=None, limit=100) -> list
    async def scan_items(filter_expression=None, limit=100) -> list
    async def batch_write(items) -> bool
```

Uses aioboto3 resources API with `dynamodb_service = DynamoDBService()` global instance.

## Code Usage Examples

### 1. Create the table (idempotent)

```python
await dynamodb_service.create_table()
# Creates table with pk/sk keys + GSI1, BillingMode=PAY_PER_REQUEST
```

### 2. Put an item with GSI

```python
await dynamodb_service.put_item(
    pk="USER#123",
    sk="ITEM#456",
    data={"name": "Laptop", "price": 999},
    gsi1pk="CATEGORY#electronics",
    gsi1sk="PRICE#999",
)
```

### 3. Get an item

```python
item = await dynamodb_service.get_item("USER#123", "ITEM#456")
# -> {pk, sk, data, created_at, updated_at, gsi1pk, gsi1sk}
```

### 4. Query by partition key (with pagination)

```python
result = await dynamodb_service.query_items(
    pk="USER#123",
    sk_prefix="ITEM#",
    limit=50,
)
items = result["items"]
last_key = result["last_evaluated_key"]  # pass back for next page
```

### 5. Query the GSI

```python
items = await dynamodb_service.query_gsi1(
    gsi1pk="CATEGORY#electronics",
    gsi1sk_prefix="PRICE#",
)
```

### 6. Batch write

```python
await dynamodb_service.batch_write([
    {"pk": "USER#123", "sk": "ITEM#1", "data": {"qty": 2}},
    {"pk": "USER#123", "sk": "ITEM#2", "data": {"qty": 5}},
])
```

## API Endpoints

| Method | Endpoint | Auth | Description |
|--------|----------|------|-------------|
| `POST` | `/api/v1/aws/dynamodb/table` | Superuser | Create table |
| `POST` | `/api/v1/aws/dynamodb/items` | Superuser | Put item (body: `pk`, `sk`, `data`, `gsi1pk?`, `gsi1sk?`) |
| `GET` | `/api/v1/aws/dynamodb/items/{pk}/{sk}` | Superuser | Get item |
| `POST` | `/api/v1/aws/dynamodb/query` | Superuser | Query (body: `pk`, `sk_prefix?`, `limit?`) |

## LocalStack Setup

```bash
# Create table
aws --endpoint-url=http://localhost:4566 dynamodb create-table \
    --table-name fastapi-items \
    --attribute-definitions AttributeName=pk,AttributeType=S AttributeName=sk,AttributeType=S \
    --key-schema AttributeName=pk,KeyType=HASH AttributeName=sk,KeyType=RANGE \
    --billing-mode PAY_PER_REQUEST \
    --region us-east-1

# List tables
aws --endpoint-url=http://localhost:4566 dynamodb list-tables --region us-east-1

# Put item
aws --endpoint-url=http://localhost:4566 dynamodb put-item \
    --table-name fastapi-items \
    --item '{"pk": {"S": "USER#1"}, "sk": {"S": "ITEM#1"}, "data": {"M": {"name": {"S": "Laptop"}}}}' \
    --region us-east-1

# Scan
aws --endpoint-url=http://localhost:4566 dynamodb scan --table-name fastapi-items --region us-east-1
```

## IAM Policy (production)

```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Action": [
        "dynamodb:GetItem",
        "dynamodb:PutItem",
        "dynamodb:UpdateItem",
        "dynamodb:DeleteItem",
        "dynamodb:Query",
        "dynamodb:Scan",
        "dynamodb:BatchWriteItem",
        "dynamodb:DescribeTable"
      ],
      "Resource": [
        "arn:aws:dynamodb:us-east-1:123456789012:table/fastapi-items",
        "arn:aws:dynamodb:us-east-1:123456789012:table/fastapi-items/index/*"
      ]
    }
  ]
}
```

## Best Practices

1. **Single-table design** — avoid one table per entity; group related items with `pk`/`sk` prefixes.
2. **Use GSIs sparingly** — each GSI adds write cost; only add when a query pattern demands it.
3. **Prefer `Query` over `Scan`** — scans read the whole table; queries use keys efficiently.
4. **Use pagination** — `LastEvaluatedKey` prevents large in-memory reads.
5. **On-demand capacity (`PAY_PER_REQUEST`)** — good default for variable/unpredictable traffic.
6. **Design keys with access patterns** — `USER#123` → `ITEM#456` supports "get all user items" naturally.
7. **Handle throttling with retries** — the AWS SDK retries `ProvisionedThroughputExceededException` automatically.
8. **Time-to-live (TTL)** — enable TTL on session/counter data for automatic cleanup.
9. **Streams** — enable DynamoDB Streams to trigger Lambda on changes (event-driven pattern).

## Common Errors

| Error | Cause | Fix |
|-------|-------|-----|
| `ResourceNotFoundException` | Table doesn't exist | Run `create_table()` first |
| `ValidationException` | Item missing required key attrs | Ensure `pk` and `sk` present |
| `ConditionalCheckFailedException` | Condition not met on put/update | Check conditional expressions |
| `ProvisionedThroughputExceededException` | Exceeded capacity | Use on-demand, retry, or backoff |
| `ThrottlingException` | Hot partition | Redesign keys for even distribution |

---

← Back to [Docs Index](README.md) · Next: [SQS Guide](sqs-guide.md)
