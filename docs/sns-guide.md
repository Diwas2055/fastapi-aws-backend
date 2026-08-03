# SNS — Pub/Sub Notifications

## What is SNS?

**Amazon Simple Notification Service (SNS)** is a fully managed **publish/subscribe messaging service**. Producers publish messages to *topics*; SNS fans each message out to all *subscribers* (HTTP/S endpoints, SQS queues, Lambda functions, email, SMS, mobile push).

## Why We Use It Here

In this FastAPI backend, SNS is the **event/notification bus**:

- Fan-out important events (order placed, user registered, item created) to multiple consumers at once
- Trigger integrations: notify an SQS queue (async processing), a Lambda (reaction), an email/SMS (user notification)
- Decouple event producers from consumers — adding a new subscriber requires no code change in the producer
- Deliver with retries and configurable message filtering per subscription

## How It Works in the App

### Architecture

```
            publish                ┌─────────────┐
┌──────────┐  ───────────────────▶ │   SNS       │
│   App    │                       │   Topic     │
└──────────┘                       └──────┬──────┘
                                          │ fan-out
                     ┌────────────────────┼─────────────────────┐
                     ▼                    ▼                     ▼
              ┌────────────┐       ┌────────────┐        ┌─────────────┐
              │ SQS Queue   │       │ Lambda     │        │ Email / SMS │
              │ (async work)│       │ (reaction) │        │ (notify user)│
              └────────────┘       └────────────┘        └─────────────┘
```

### Topic Configuration

```python
# app/core/config.py
SNS_TOPIC_ARN: Optional[str] = None    # e.g., arn:aws:sns:us-east-1:000000000000:fastapi-notifications
```

| Config | Default | Purpose |
|--------|---------|---------|
| `SNS_TOPIC_ARN` | `None` | Topic ARN (must be set before publish/subscribe) |

> Region comes from the shared `AWS_REGION` setting.

### Service Class

```python
# app/services/aws/sns_service.py
class SNSService:
    async def create_topic(name) -> str | None                          # returns topic ARN
    async def publish(message: str, subject=None, message_attributes=None, topic_arn=None) -> dict | None
    async def publish_batch(messages: list, topic_arn=None) -> dict      # loops publish()
    async def subscribe(protocol, endpoint, topic_arn=None, filter_policy=None) -> str | None
    async def unsubscribe(subscription_arn) -> bool
    async def list_subscriptions(topic_arn=None) -> list
    async def add_permission(label, aws_account_ids, actions, topic_arn=None) -> bool
```

Uses **aioboto3** with `sns_service = SNSService()` global instance.

## Code Usage Examples

### 1. Publish a plain message

```python
from app.services.aws import sns_service

result = await sns_service.publish(
    message='{"event": "item.created", "item_id": 456, "user_id": 42}',
    subject="upload-notification",
)
# -> {"message_id": "..."}
```

> `message` is a string. For structured events, publish a JSON string and have subscribers parse it (see example 3).

### 2. Publish a batch of messages

```python
await sns_service.publish_batch([
    {"message": '{"event": "order.placed", "id": 1}', "subject": "order"},
    {"message": '{"event": "user.registered", "id": 7}', "subject": "user"},
])
# -> {"successful": [...], "failed": [...]}
```

### 3. Publish with message attributes (for filter policies)

```python
await sns_service.publish(
    message='{"order_id": 1, "total": 99.0}',
    subject="order.placed",
    message_attributes={
        "event_type": {"DataType": "String", "StringValue": "order"},
        "priority":  {"DataType": "Number", "StringValue": "1"},
    },
)
```

### 4. Subscribe an endpoint (SQS queue, Lambda, email, SMS...)

```python
# SQS queue (fan-out to async worker)
await sns_service.subscribe(
    protocol="sqs",
    endpoint="arn:aws:sqs:us-east-1:000000000000:fastapi-queue",
)

# Email (must confirm the subscription link emailed to the address)
await sns_service.subscribe(protocol="email", endpoint="ops@example.com")

# Lambda function
await sns_service.subscribe(
    protocol="lambda",
    endpoint="arn:aws:lambda:us-east-1:000000000000:function:reactor",
)

# With a filter policy (only deliver order events)
await sns_service.subscribe(
    protocol="sqs",
    endpoint="arn:aws:sqs:us-east-1:000000000000:fastapi-queue",
    filter_policy={"event_type": ["order"]},
)
```

### 5. Unsubscribe / list / cross-account access

```python
await sns_service.unsubscribe("arn:aws:sns:us-east-1:...:sub")
subs = await sns_service.list_subscriptions()
await sns_service.add_permission(
    label="allow-account-1234",
    aws_account_ids=["123456789012"],
    actions=["Publish"],
)
```

## API Endpoints

| Method | Endpoint | Auth | Description |
|--------|----------|------|-------------|
| `POST` | `/api/v1/aws/sns/publish` | Superuser | Publish message (body: `message`, `subject`?, `message_attributes`?) |

## LocalStack Setup

```bash
# Create topic
aws --endpoint-url=http://localhost:4566 sns create-topic --name fastapi-notifications --region us-east-1

# Publish (use the TopicArn from above)
aws --endpoint-url=http://localhost:4566 sns publish \
    --topic-arn arn:aws:sns:us-east-1:000000000000:fastapi-notifications \
    --message '{"event":"item.created"}' \
    --region us-east-1

# List topics
aws --endpoint-url=http://localhost:4566 sns list-topics --region us-east-1

# Subscribe an email (LocalStack prints confirmation URL)
aws --endpoint-url=http://localhost:4566 sns subscribe \
    --topic-arn arn:aws:sns:us-east-1:000000000000:fastapi-notifications \
    --protocol email \
    --notification-endpoint ops@example.com \
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
        "sns:Publish",
        "sns:CreateTopic",
        "sns:Subscribe",
        "sns:ListTopics",
        "sns:ListSubscriptionsByTopic"
      ],
      "Resource": [
        "arn:aws:sns:us-east-1:123456789012:fastapi-notifications",
        "arn:aws:sns:us-east-1:123456789012:fastapi-notifications:*"
      ]
    }
  ]
}
```

## Best Practices

1. **One event per message** — keep payloads small and semantic (`event`, `entity`, `payload`).
2. **Use message attributes** for subscription filtering (deliver only relevant events to each subscriber).
3. **Fan-out to SQS for async work** — SNS → SQS gives durability + retries + no lost messages.
4. **Configure retry policies** — SNS retries failed HTTP/S and Lambda deliveries with exponential backoff.
5. **Use DLQs** — subscribe endpoints with a dead-letter queue to catch undeliverable messages.
6. **Message ordering** — SNS is best-effort ordering; use FIFO topics if strict ordering is required.
7. **Don't publish user PII** to email/SMS topics without consent/limits.
8. **Idempotency in subscribers** — SNS may deliver duplicates; make consumers idempotent.

## Common Errors

| Error | Cause | Fix |
|-------|-------|-----|
| `NotFound` / topic missing | `SNS_TOPIC_ARN` wrong or unset | Create topic / set ARN |
| `AuthorizationError` | IAM lacks `sns:Publish` | Update IAM policy |
| `InvalidParameter` | Bad subject/attrs | Validate message attributes types |
| `SubscriptionLimitExceeded` | Too many subscribers | Reduce subscribers / raise limit |
| Email not received | Email subscription unconfirmed | Click confirmation link sent to the address |

---

[← Back to Docs Index](README.md) · [Next: Secrets Manager Guide](secrets-manager-guide.md)
