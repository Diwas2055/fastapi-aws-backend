# SigNoz — Observability and APM

## What It Is

SigNoz is an open-source observability platform. It collects three types of data from your application:

- **Traces** — shows the path of a request through your code
- **Metrics** — numbers like CPU usage, memory, request counts
- **Logs** — text records of events and errors

All three are stored in ClickHouse and shown in one web UI.

## Why We Use It

This FastAPI backend needs visibility into:

- Which endpoints are slow
- Where database queries take time
- How external AWS calls perform
- What errors happen in production
- How services depend on each other

Without observability, you only know something is wrong when users report it. SigNoz lets you see problems before users do.

## What It Replaces

| Before | After |
|--------|-------|
| Separate tools for logs, metrics, traces | One tool for all three |
| Guesswork for slow requests | Exact trace showing slow query or AWS call |
| No visibility into errors | Automatic exception tracking |
| Manual log searching | Searchable logs linked to traces |

---

## Why SigNoz is Popular

### Advantages

**Native OpenTelemetry**
- Uses OpenTelemetry standard. No vendor lock-in. Can switch to other backends later.

**Metrics**
- Collects RED metrics: Rate, Errors, Duration for every endpoint.
- Monitors database query performance.
- Tracks Celery task success/failure rates.

**Logs**
- Collects application logs with trace IDs attached.
- Search and filter logs by service, severity, time range.
- Correlate logs with traces and metrics.

**Traces**
- Records the full path of each request.
- Shows time spent in each function, DB query, and external call.
- Identifies slow database queries or slow AWS service calls.

**Service Map**
- Auto-generated map of all services and how they call each other.
- Shows traffic flow between FastAPI, PostgreSQL, Redis, Celery, and AWS services.

**Distributed Tracing**
- Traces requests across multiple services.
- For example: API call → Celery task → S3 upload → SQS message → Lambda invocation.

**Dependency Graph**
- Visual map of internal and external dependencies.
- Shows which databases, caches, and AWS services your app relies on.

**APM (Application Performance Monitoring)**
- Monitor application health in real time.
- Track p95/p99 latencies, error rates, throughput.

**Exception Tracking**
- Automatically captures unhandled exceptions.
- Groups similar errors together.
- Shows stack traces and request context.

**ClickHouse Backend**
- ClickHouse is a columnar database built for analytics.
- Handles large volumes of trace and metric data efficiently.
- Fast aggregation and time-series queries.

**One UI**
- All observability data in one place. No switching between Grafana, Prometheus, ELK, etc.
- Traces, metrics, logs, and alerts in a single dashboard.

---

## How It Works

### Architecture

```
FastAPI App ──(OTLP)──▶ SigNoz Collector ──▶ ClickHouse
                                  │
                                  └──▶ SigNoz UI (port 3301)
```

### Data Flow

1. FastAPI app emits traces, metrics, and logs using OpenTelemetry SDK
2. Data is sent to SigNoz via OTLP protocol (port 4317 gRPC or 4318 HTTP)
3. SigNoz stores data in ClickHouse
4. SigNoz UI queries ClickHouse and displays dashboards

---

## Configuration

### Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `SIGNOZ_ENABLED` | `true` | Enable/disable SigNoz instrumentation |
| `SIGNOZ_OTLP_ENDPOINT` | `http://localhost:4318` | SigNoz OTLP endpoint |
| `SIGNOZ_SERVICE_NAME` | `fastapi-aws-backend` | Service name in SigNoz |
| `SIGNOZ_SERVICE_VERSION` | `1.0.0` | Service version |
| `SIGNOZ_DEPLOYMENT_ENVIRONMENT` | `development` | Environment label |
| `SIGNOZ_TRACING_SAMPLE_RATE` | `1.0` | Fraction of traces to sample (0.0 to 1.0) |
| `SIGNOZ_UI_URL` | `http://localhost:3301` | SigNoz UI URL |

### Docker Compose

SigNoz is included in both `docker-compose.yml` and `docker-compose.prod.yml`.

```yaml
signoz:
  image: signoz/signoz:latest
  ports:
    - "4317:4317"   # OTLP gRPC
    - "4318:4318"   # OTLP HTTP
    - "3301:3301"   # SigNoz UI
  volumes:
    - signoz_data:/var/lib/signoz
```

### Production Configuration

For production, use a lower trace sample rate to reduce data volume:

```bash
SIGNOZ_TRACING_SAMPLE_RATE=0.1  # Sample 10% of traces
SIGNOZ_DEPLOYMENT_ENVIRONMENT=production
```

SigNoz stores data in ClickHouse. For production:
- Use persistent volume for `signoz_data`
- Configure ClickHouse backup strategy
- Set retention policies in SigNoz settings
- Monitor ClickHouse disk usage

---

## Usage

### Starting SigNoz

```bash
# Start all services including SigNoz
docker-compose up -d

# Verify SigNoz is running
curl http://localhost:3301

# Check OTLP endpoint
curl http://localhost:4318/v1/traces
```

### Accessing SigNoz UI

Open http://localhost:3301 in your browser.

First time setup:
1. Create an account
2. Set up your organization
3. Configure data retention (default: 7 days for traces)

### Viewing Traces

1. Go to **Traces** in the left sidebar
2. Filter by service name: `fastapi-aws-backend`
3. Click any trace to see the full waterfall
4. Each span shows:
   - Duration
   - Service/operation name
   - Tags (endpoint, method, status code)
   - Events (exceptions, logs)

### Viewing Metrics

1. Go to **Metrics** in the left sidebar
2. Select a metric like `http.server.request.duration`
3. Filter by service and time range
4. Create custom dashboards

### Viewing Logs

1. Go to **Logs** in the left sidebar
2. Search by trace ID, service, or keyword
3. Click a log line to jump to the related trace

### Service Map

1. Go to **Services** in the left sidebar
2. See all services and their dependencies
3. Click a service to see:
   - Traffic flow
   - Error rates
   - Latency percentiles
   - Top dependencies

---

## Instrumented Components

The following components are automatically instrumented:

| Component | What Gets Traced |
|-----------|-----------------|
| FastAPI | Every request/response, route handler duration |
| SQLAlchemy | Every database query, connection pool usage |
| Redis | Every Redis command, latency |
| HTTPX | Outbound HTTP requests to AWS services |
| Celery | Task execution, queue latency |
| Logging | Log events with trace IDs attached |

---

## Production Grade Configuration

### Resource Limits

```yaml
# docker-compose.prod.yml
signoz:
  deploy:
    replicas: 1
    resources:
      limits:
        memory: 2G
        cpus: '1.0'
      reservations:
        memory: 1G
        cpus: '0.5'
```

### Environment Settings

```bash
# Production
SIGNOZ_ENABLED=true
SIGNOZ_OTLP_ENDPOINT=http://signoz:4318
SIGNOZ_SERVICE_NAME=fastapi-aws-backend
SIGNOZ_SERVICE_VERSION=1.0.0
SIGNOZ_DEPLOYMENT_ENVIRONMENT=production
SIGNOZ_TRACING_SAMPLE_RATE=0.1
SIGNOZ_UI_URL=http://signoz:3301
```

### Sampling Strategy

| Environment | Sample Rate | Reason |
|-------------|-------------|--------|
| Development | `1.0` | Capture all traces for debugging |
| Staging | `0.5` | Capture half of traces |
| Production | `0.1` | Capture 10% to reduce storage costs |

### Data Retention

Configure in SigNoz UI under **Settings > General**:
- **Traces**: 7-30 days
- **Metrics**: 90 days
- **Logs**: 7-30 days

### High Availability

For production, run multiple SigNoz replicas:

```yaml
signoz:
  deploy:
    replicas: 2
    update_config:
      parallelism: 1
      delay: 10s
```

### Backup

ClickHouse data is stored in `signoz_data` volume. Back up this volume regularly:

```bash
# Backup ClickHouse data
docker-compose exec signoz clickhouse-backup create signoz-backup
```

---

## SigNoz vs CloudWatch

| Feature | SigNoz | CloudWatch |
|---------|--------|------------|
| Open source | Yes | No |
| OpenTelemetry | Native | Partial |
| Self-hosted | Yes | No |
| Traces | Full distributed tracing | X-Ray only |
| Logs | Included | Separate service |
| Metrics | Included | Included |
| Cost | Infrastructure only | Per GB ingested |
| Service Map | Built-in | Requires X-Ray |

Use both if needed:
- SigNoz for deep APM and distributed tracing
- CloudWatch for AWS-native metrics and alarms

---

## Common Issues

| Issue | Cause | Fix |
|-------|-------|-----|
| No traces in SigNoz | `SIGNOZ_ENABLED=false` | Set to `true` |
| Connection refused | SigNoz not running | `docker-compose up signoz` |
| High memory usage | Sample rate too high | Lower `SIGNOZ_TRACING_SAMPLE_RATE` |
| Missing DB traces | SQLAlchemy not instrumented | Check `engine` passed to setup |
| UI not loading | Port conflict | Check port 3301 availability |

---

## Useful Commands

```bash
# Start SigNoz only
docker-compose up -d signoz

# View SigNoz logs
docker-compose logs -f signoz

# Check SigNoz health
curl http://localhost:3301/api/v1/health

# Stop SigNoz
docker-compose stop signoz
```

---

← Back to [Docs Index](README.md) · Next: [All Services Architecture](aws-architecture.md)
