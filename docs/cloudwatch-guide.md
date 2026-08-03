# CloudWatch — Monitoring and Logging

## What is CloudWatch?

**Amazon CloudWatch** is AWS's monitoring and observability service. It collects and tracks **metrics**, **logs**, and **events** from AWS resources and your application, triggers **alarms**, and visualizes data in dashboards.

## Why We Use It Here

In this FastAPI backend, CloudWatch is the **observability layer**:

- **Metrics** — emit custom application metrics (request counts, error rates, processing times, business events)
- **Logs** — ship structured application logs (JSON) to CloudWatch Logs for search, retention, and alerting
- **Alarms** — alert on anomalies (high error rate, latency spikes, queue depth)
- **Dashboards** — one place to view app health, API performance, and AWS resource utilization

## How It Works in the App

### Architecture

```
┌──────────────┐  put_metric_data  ┌────────────────┐   ┌──────────────┐
│   FastAPI    │ ────────────────▶ │  CloudWatch    │   │  Alarm       │──▶ SNS → notify
│    app       │                   │  Metrics       │   └──────────────┘
│              │  put_log_events   ├────────────────┤
│              │ ────────────────▶ │  CloudWatch    │
│              │                   │  Logs          │──▶ search / dashboard
└──────────────┘                   └────────────────┘
```

### Configuration

```python
# app/core/config.py
CLOUDWATCH_LOG_GROUP: str = "/aws/fastapi/app"
CLOUDWATCH_LOG_STREAM: str = "application"      # e.g., application, worker, per-service
```

| Config | Default | Purpose |
|--------|---------|---------|
| `CLOUDWATCH_LOG_GROUP` | `/aws/fastapi/app` | Log group name |
| `CLOUDWATCH_LOG_STREAM` | `application` | Log stream within the group |

### Service Class

```python
# app/services/aws/cloudwatch_service.py
class CloudWatchService:
    # Metrics
    async def put_metric(namespace, name, value, unit="Count", dimensions=None) -> bool
    async def put_metric_data(namespace, metric_data: list) -> bool             # batch
    async def get_metric_statistics(namespace, metric_name, start_time, end_time, period=300, statistics=None) -> dict | None

    # Logs
    async def create_log_group(log_group_name=None) -> bool
    async def create_log_stream(log_group_name=None, log_stream_name=None) -> bool
    async def put_log_event(message: str, level="INFO", log_group_name=None, log_stream_name=None) -> bool
    async def put_log_events(log_events: list, log_group_name=None, log_stream_name=None) -> bool
    async def get_log_events(start_time=None, end_time=None, limit=100, log_group_name=None, log_stream_name=None) -> list
    async def filter_log_events(filter_pattern, start_time=None, end_time=None, limit=100, log_group_name=None) -> list

    # Dashboards & Alarms
    async def put_dashboard(name, dashboard_body: dict) -> bool
    async def list_dashboards() -> list
    async def put_alarm(name, metric_name, namespace, threshold, comparison_operator="GreaterThanThreshold", evaluation_periods=1, period=300, statistic="Average", alarm_actions=None) -> bool
    async def describe_alarms() -> list
```

Uses **aioboto3** with `cloudwatch_service = CloudWatchService()` global instance. Two clients internally: `cloudwatch` (metrics/dashboards/alarms) and `logs` (logs).

## Code Usage Examples

### 1. Emit a metric

```python
from app.services.aws import cloudwatch_service

await cloudwatch_service.put_metric(
    namespace="FastAPI",
    name="RequestCount",
    value=1,
    unit="Count",
)
await cloudwatch_service.put_metric(
    namespace="FastAPI",
    name="P99Latency",
    value=0.312,
    unit="Seconds",
    dimensions=[{"Name": "endpoint", "Value": "/items"}],
)
```

### 2. Batch multiple metrics in one call

```python
await cloudwatch_service.put_metric_data(
    namespace="FastAPI",
    metric_data=[
        {"MetricName": "OrderPlaced",   "Value": 1,     "Unit": "Count",   "Timestamp": ...},
        {"MetricName": "OrderValue",    "Value": 129.5, "Unit": "None",    "Timestamp": ...},
        {"MetricName": "PaymentFailed", "Value": 0,     "Unit": "Count",   "Timestamp": ...},
    ],
)
```

### 3. Write a log event

```python
await cloudwatch_service.put_log_event(
    message="Item 456 created",
    level="INFO",
)
# Stored as JSON: {"level": "INFO", "message": "Item 456 created", "timestamp": "..."}
```

### 4. Write a batch of log events

```python
await cloudwatch_service.put_log_events([
    {"timestamp": int(datetime.now(UTC).timestamp() * 1000), "message": "first"},
    {"timestamp": int(datetime.now(UTC).timestamp() * 1000), "message": "second"},
])
```

### 5. Search logs (filter pattern)

```python
hits = await cloudwatch_service.filter_log_events(
    filter_pattern='"ERROR"',
    limit=20,
)
```

### 6. Get recent log events

```python
events = await cloudwatch_service.get_log_events(limit=50)
```

### 7. Create a dashboard and an alarm

```python
await cloudwatch_service.put_dashboard(
    name="FastAPI-Overview",
    dashboard_body={"widgets": [{"type": "metric", ...}]},
)

await cloudwatch_service.put_alarm(
    name="HighErrorRate",
    metric_name="ErrorCount",
    namespace="FastAPI",
    threshold=100,
    comparison_operator="GreaterThanThreshold",
    evaluation_periods=1,
    period=300,
    statistic="Sum",
    alarm_actions=["arn:aws:sns:us-east-1:000000000000:fastapi-notifications"],
)

alarms = await cloudwatch_service.describe_alarms()
```

## API Endpoints

| Method | Endpoint | Auth | Description |
|--------|----------|------|-------------|
| `POST` | `/api/v1/aws/cloudwatch/metric` | Superuser | Emit metric (body: `namespace`, `name`, `value`, `unit`?, `dimensions`?) |
| `POST` | `/api/v1/aws/cloudwatch/log?message=&level=` | Superuser | Write log event (query params) |
| `GET` | `/api/v1/aws/cloudwatch/logs?hours=&limit=` | Superuser | Fetch recent log events (query params; `hours` 1–168, `limit` 1–1000) |

### Example requests

```bash
# Put a metric
curl -X POST http://localhost:8000/api/v1/aws/cloudwatch/metric \
  -H "Authorization: Bearer <superuser-token>" -H "Content-Type: application/json" \
  -d '{"namespace": "FastAPI", "name": "RequestCount", "value": 1, "unit": "Count"}'

# Write a log event
curl -X POST "http://localhost:8000/api/v1/aws/cloudwatch/log?message=Item%20456%20created&level=INFO" \
  -H "Authorization: Bearer <superuser-token>"

# Get logs from the last 24 hours
curl -X GET "http://localhost:8000/api/v1/aws/cloudwatch/logs?hours=24&limit=100" \
  -H "Authorization: Bearer <superuser-token>"
```

## LocalStack Setup

```bash
# Create log group + stream
aws --endpoint-url=http://localhost:4566 logs create-log-group \
    --log-group-name /fastapi/backend --region us-east-1
aws --endpoint-url=http://localhost:4566 logs create-log-stream \
    --log-group-name /fastapi/backend --log-stream-name api --region us-east-1

# Put metric data
aws --endpoint-url=http://localhost:4566 cloudwatch put-metric-data \
    --namespace FastAPI --metric-name RequestCount --value 1 --region us-east-1

# Get metric statistics
aws --endpoint-url=http://localhost:4566 cloudwatch get-metric-statistics \
    --namespace FastAPI --metric-name RequestCount \
    --start-time 2026-01-01T00:00:00Z --end-time 2026-08-03T00:00:00Z --period 300 --statistics Sum \
    --region us-east-1

# List log events
aws --endpoint-url=http://localhost:4566 logs get-log-events \
    --log-group-name /fastapi/backend --log-stream-name api --region us-east-1
```

## IAM Policy (production)

```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Action": [
        "cloudwatch:PutMetricData",
        "cloudwatch:GetMetricStatistics",
        "cloudwatch:ListMetrics",
        "cloudwatch:PutMetricAlarm",
        "cloudwatch:DescribeAlarms",
        "logs:CreateLogGroup",
        "logs:CreateLogStream",
        "logs:PutLogEvents",
        "logs:GetLogEvents",
        "logs:StartQuery",
        "logs:GetQueryResults"
      ],
      "Resource": "*"
    }
  ]
}
```

> `logs:PutLogEvents` resource should be scoped to the specific log group/stream ARN when possible. `cloudwatch:PutMetricData` is always `*` (metrics have no ARN).

## Best Practices

1. **Use structured (JSON) logs** — the app logs key/value pairs for searchable, parseable output.
2. **Batch metric/label writes** — `put_metric_data` supports up to 1,000 values per request; batch to reduce calls and cost.
3. **Choose appropriate resolution** — standard (60s) for most metrics; high-resolution (1s) only when needed (costs more).
4. **Never log secrets** — redact passwords, tokens, and PII before emitting logs.
5. **Set alarms on business signals** — error rate, queue depth, 5xx count, and P99 latency (not just CPU).
6. **Define retention** — set log retention (e.g., 30 days) to control cost; logs grow fast.
7. **Tag metrics** — add dimensions (`service`, `environment`, `endpoint`) to slice/dice in dashboards.
8. **Use Logs Insights** for fast text search over large volumes instead of `get_log_events`.
9. **Correlate with traces** — include request ID in every log line to link logs to specific requests.

## Common Errors

| Error | Cause | Fix |
|-------|-------|-----|
| `ResourceNotFoundException` | Log group/stream missing | Create group + stream first |
| `InvalidParameterValueException` | Bad unit/dimension | Validate metric names and units |
| `DataAlreadyAcceptedException` | Replaying old log sequence token | Use latest `nextSequenceToken` |
| `InvalidSequenceTokenException` | Sequence token out of order | Retry with the returned token |
| `ThrottlingException` | Too many PutLogEvents | Batch logs and add backoff |
| `ServiceUnavailable` | Transient AWS issue | Retry with exponential backoff |

---

[← Back to Docs Index](README.md) · [Next: AWS Architecture Overview](aws-architecture.md)
