# SQS — Message Queuing for Async Processing

## What is SQS?

**Amazon Simple Queue Service (SQS)** is a fully managed message queue for decoupling application components. It lets you send, store, and receive messages between software components without losing messages or requiring each component to be always available.

## Why We Use It Here

In this FastAPI backend, SQS is the **asynchronous work queue**:

- Offload long-running work (file processing, notifications, report generation) from the API request path
- Buffer bursts of traffic — producers keep working even if consumers are down
- Guarantee delivery — messages persist for up to 4–14 days until processed
- Work with SNS (fan-out → queue subscription) and Celery workers as consumers

## How It Works in the App

### Architecture

```
┌────────────┐   send_message   ┌─────────┐   receive + delete   ┌──────────────┐
│  API / App │ ───────────────▶ │  SQS    │ ───────────────────▶ │ Celery Worker │
└────────────┘                  │ Queue   │                      └──────────────┘
       └── SNS fan-out ─────────▶│  Q1/Q2  │
```

- **Producer** (API): `sqs_service.send_message(...)` on request
- **Consumer** (worker): receives, processes, then deletes the message (`receive_messages` → process → `delete_message`)

### Queue Configuration

```python
# app/core/config.py
SQS_QUEUE_URL: Optional[str] = None        # e.g., http://localhost:4566/000000000000/fastapi-queue
SQS_VISIBILITY_TIMEOUT: int = 300          # seconds a message is hidden while processing
SQS_MAX_RECEIVE_COUNT: int = 3             # delivery attempts before DLQ
```

| Config | Default | Purpose |
|--------|---------|---------|
| `SQS_QUEUE_URL` | `None` | Full queue URL (must be set before send/receive) |
| `SQS_VISIBILITY_TIMEOUT` | `300` | Message hidden from other consumers while processing (also set on queue creation) |
| `SQS_MAX_RECEIVE_COUNT` | `3` | Max deliveries before message → DLQ |

### Service Class

```python
# app/services/aws/sqs_service.py
class SQSService:
    async def create_queue(queue_name) -> str | None        # returns queue URL
    async def send_message(message_body, delay_seconds=0, message_attributes=None, queue_url=None) -> dict | None
    async def send_batch(messages: list, queue_url=None) -> dict          # max 10
    async def receive_messages(max_messages=10, wait_time_seconds=20, queue_url=None) -> list
    async def delete_message(receipt_handle, queue_url=None) -> bool
    async def delete_messages_batch(receipt_handles: list, queue_url=None) -> dict
    async def change_visibility(receipt_handle, visibility_timeout, queue_url=None) -> bool
    async def get_queue_attributes(queue_url=None) -> dict | None
```

Uses **aioboto3** with `sqs_service = SQSService()` global instance. Queue URL comes from `SQS_QUEUE_URL`; long-polling (`ReceiveMessageWaitTimeSeconds=20`) and 14-day retention are baked into `create_queue`.

## Code Usage Examples

### 1. Send a message

```python
from app.services.aws import sqs_service

result = await sqs_service.send_message(
    message_body={"event": "file_uploaded", "key": "items/123/report.pdf", "user_id": 42},
    delay_seconds=0,
)
# -> {"message_id": "...", "md5_of_body": "...", "sequence_number": None}
```

### 2. Send a batch (up to 10 messages)

```python
await sqs_service.send_batch([
    {"body": {"x": 1}},
    {"body": {"x": 2}, "delay": 5, "attributes": {"priority": {"DataType": "String", "StringValue": "low"}}},
])
# -> {"successful": [...], "failed": [...]}
```

### 3. Receive messages (polling loop in a worker)

```python
messages = await sqs_service.receive_messages(
    max_messages=10,
    wait_time_seconds=20,   # long poll
)
for msg in messages:
    try:
        process(msg["Body"])                                # do the work
        await sqs_service.delete_message(msg["ReceiptHandle"])  # ACK
    except Exception:
        await sqs_service.change_visibility(msg["ReceiptHandle"], 60)  # retry later
```

> The message **Body** is a JSON string — parse with `json.loads()`. Delete only after successful processing; otherwise the message reappears after the visibility timeout.

### 4. Batch delete / inspect the queue

```python
await sqs_service.delete_messages_batch(["handle-1", "handle-2"])
attrs = await sqs_service.get_queue_attributes()
# -> {"ApproximateNumberOfMessages": "0", "VisibilityTimeout": "300", ...}
```

## Integration with SNS (fan-out pattern)

Subscribe an SQS queue to an SNS topic so notifications are persisted and processed asynchronously:

```python
# SNS: publish to topic
await sns_service.publish('{"order_id": 1}')

# SQS: queue subscribed to the topic receives it, worker processes
```

## API Endpoints

| Method | Endpoint | Auth | Description |
|--------|----------|------|-------------|
| `POST` | `/api/v1/aws/sqs/send` | Superuser | Send message (body: `message_body`, `delay_seconds`?, `message_attributes`?) |
| `POST` | `/api/v1/aws/sqs/receive?max_messages=&wait_time=` | Superuser | Receive messages (query params; `max_messages` 1–10, `wait_time` 0–20) |

### Example request

```bash
# Send
curl -X POST http://localhost:8000/api/v1/aws/sqs/send \
  -H "Authorization: Bearer <superuser-token>" \
  -H "Content-Type: application/json" \
  -d '{"message_body": {"event": "file_uploaded", "key": "a.pdf"}, "delay_seconds": 0}'

# Receive (long poll up to 20s)
curl -X POST "http://localhost:8000/api/v1/aws/sqs/receive?max_messages=10&wait_time=20" \
  -H "Authorization: Bearer <superuser-token>"
```

## LocalStack Setup

```bash
# Create queue
aws --endpoint-url=http://localhost:4566 sqs create-queue --queue-name fastapi-queue --region us-east-1

# Send message
aws --endpoint-url=http://localhost:4566 sqs send-message \
    --queue-url http://localhost:4566/000000000000/fastapi-queue \
    --message-body '{"hello":"world"}' \
    --region us-east-1

# Receive message
aws --endpoint-url=http://localhost:4566 sqs receive-message \
    --queue-url http://localhost:4566/000000000000/fastapi-queue \
    --region us-east-1

# Delete message (after processing) — use the ReceiptHandle
aws --endpoint-url=http://localhost:4566 sqs delete-message \
    --queue-url http://localhost:4566/000000000000/fastapi-queue \
    --receipt-handle <RECEIPT_HANDLE> \
    --region us-east-1
```

## IAM Policy (production)

```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Action": [
        "sqs:SendMessage",
        "sqs:ReceiveMessage",
        "sqs:DeleteMessage",
        "sqs:GetQueueAttributes",
        "sqs:GetQueueUrl"
      ],
      "Resource": "arn:aws:sqs:us-east-1:123456789012:fastapi-queue"
    }
  ]
}
```

## Best Practices

1. **Long polling** (`WaitTimeSeconds=20`) — reduces empty receives and API calls (cost savings).
2. **Visibility timeout** ≈ processing time × 6 — prevents a slow consumer from being retried prematurely.
3. **Dead-letter queue (DLQ)** — set `maxReceiveCount` (5) and route failures to a DLQ for inspection.
4. **Idempotent consumers** — SQS delivers *at least once*; your worker must tolerate duplicates (e.g., dedupe by message ID or business key).
5. **`ReceiptHandle` delete after processing** — only delete when the work completed successfully.
6. **Delay queues / message timers** — schedule work up to 15 minutes ahead.
7. **Batch with care** — `send_message_batch` max 10 messages, 256 KB per message, 1 MB per batch.
8. **Never put secrets in messages** — messages are not encrypted by default; use KMS encryption for sensitive payloads.

## Common Errors

| Error | Cause | Fix |
|-------|-------|-----|
| `QueueDoesNotExist` | Queue URL wrong or queue deleted | Verify `SQS_QUEUE_URL` |
| `InvalidAddress` | Wrong endpoint / region | Check `AWS_ENDPOINT_URL` and region |
| `MessageNotInflight` | Receipt handle stale/expired | Re-receive before deleting |
| `BatchRequestTooLong` | Batch > 1 MB | Reduce batch size |
| `AccessDenied` | IAM missing `SendMessage` | Update IAM policy |

---

[← Back to Docs Index](README.md) · [Next: SNS Guide](sns-guide.md)
