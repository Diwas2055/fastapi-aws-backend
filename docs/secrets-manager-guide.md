# Secrets Manager — Secure Secret Storage

## What It Is

AWS Secrets Manager is a managed service for storing, retrieving, and rotating secrets — database credentials, API keys, OAuth tokens, connection strings. Secrets are encrypted at rest with KMS and retrievable via API or IAM role.

## Why We Use It

In this FastAPI backend, Secrets Manager is the central secrets vault:
- Store database passwords, Redis credentials, JWT signing keys, and third-party API keys outside the codebase and `.env` files
- Retrieve secrets at runtime via IAM role (ECS task role / EKS IRSA) — no secrets in the container image or repo
- Enable automatic rotation so credentials never leak or go stale
- Audit access through CloudTrail (who read which secret, when)

## How It Works

### Architecture

```
┌──────────────┐  assume role   ┌──────────────┐   GetSecretValue   ┌───────────────────┐
│ FastAPI app  │ ─────────────▶ │  IAM Role     │ ─────────────────▶ │ Secrets Manager    │
│ (ECS/EKS)    │                │ (task role)   │                    │  (KMS encrypted)   │
└──────────────┘                └──────────────┘                    └───────────────────┘
```

### Configuration

```python
# app/core/config.py
SECRETS_MANAGER_SECRET: Optional[str] = None    # name or ARN of the default secret
```

| Config | Default | Purpose |
|--------|---------|---------|
| `SECRETS_MANAGER_SECRET` | `None` | Default secret name/ARN (services always take an explicit name) |

Region comes from the shared `AWS_REGION` setting.

### Service Class

```python
# app/services/aws/secrets_service.py
class SecretsManagerService:
    async def create_secret(name, secret_value: dict, description=None, tags=None) -> str | None
    async def get_secret(name) -> dict | None                  # parsed JSON value
    async def update_secret(name, secret_value: dict) -> str | None
    async def delete_secret(name, recovery_window_days=7) -> bool
    async def list_secrets(max_results=100) -> list
    async def rotate_secret(name) -> bool
```

Uses aioboto3 with `secrets_manager_service = SecretsManagerService()` global instance.

Note: `get_secret()` returns the secret parsed as a Python dict (assumes the secret string is JSON). `create_secret` auto-updates if the secret already exists (`ResourceExistsException` → `update_secret`).

## Code Usage Examples

### 1. Create a secret

```python
from app.services.aws import secrets_manager_service

arn = await secrets_manager_service.create_secret(
    name="fastapi/prod",
    secret_value={"DB_PASSWORD": "s3cr3t", "JWT_SECRET": "jwt-key", "REDIS_URL": "redis://..."},
    description="Production credentials for FastAPI backend",
    tags=[{"Key": "env", "Value": "prod"}],
)
# -> arn:aws:secretsmanager:us-east-1:...:secret:fastapi/prod-...
```

### 2. Retrieve a secret at startup (recommended pattern)

```python
from app.services.aws import secrets_manager_service

secret = await secrets_manager_service.get_secret("fastapi/prod")
# -> {"DB_PASSWORD": "s3cr3t", "JWT_SECRET": "jwt-key", "REDIS_URL": "redis://..."}

settings.DATABASE_PASSWORD = secret["DB_PASSWORD"]
settings.JWT_SECRET = secret["JWT_SECRET"]
```

Tip: Cache the retrieved secret in memory for the app's lifetime and only re-fetch on rotation events or cache expiry — don't call the API per request.

### 3. Update / delete

```python
await secrets_manager_service.update_secret(
    "fastapi/prod",
    {"DB_PASSWORD": "new-pass", "JWT_SECRET": "jwt-key"},
)
await secrets_manager_service.delete_secret("stale/secret", recovery_window_days=7)
# Recovery window default 7 days (0 = immediate, permanent)
```

### 4. List / rotate

```python
secrets = await secrets_manager_service.list_secrets(max_results=50)
await secrets_manager_service.rotate_secret("fastapi/prod")
```

## API Endpoints

| Method | Endpoint | Auth | Description |
|--------|----------|------|-------------|
| `POST` | `/api/v1/aws/secrets` | Superuser | Create secret (body: `name`, `value` dict, `description?`) |
| `GET` | `/api/v1/aws/secrets/{name}` | Superuser | Get secret value (returns `{"value": {...}}`) |

## LocalStack Setup

```bash
# Create secret
aws --endpoint-url=http://localhost:4566 secretsmanager create-secret \
    --name fastapi/prod \
    --secret-string '{"DB_PASSWORD":"s3cr3t"}' \
    --region us-east-1

# Get secret value
aws --endpoint-url=http://localhost:4566 secretsmanager get-secret-value \
    --secret-id fastapi/prod \
    --region us-east-1

# List secrets
aws --endpoint-url=http://localhost:4566 secretsmanager list-secrets --region us-east-1
```

## IAM Policy (production)

```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Action": [
        "secretsmanager:GetSecretValue",
        "secretsmanager:DescribeSecret"
      ],
      "Resource": "arn:aws:secretsmanager:us-east-1:123456789012:secret:fastapi/*"
    }
  ]
}
```

Least privilege: the app needs `GetSecretValue` + `DescribeSecret` only. Create/update/rotate belong to a deploy-time role or admin, not the runtime role.

## Best Practices

1. **Never store secrets in code, `.env`, or Docker images** — `.env.example` files are placeholders only; production values come from Secrets Manager.
2. **Use IAM roles, not keys** — the ECS task role or EKS IRSA provides credentials automatically; no `AWS_ACCESS_KEY_ID` in the container.
3. **Cache retrieved secrets in memory** — avoid per-request API calls (latency + cost).
4. **Enable automatic rotation** — define a rotation Lambda for DB passwords; app should handle rotation gracefully (retry on auth failure).
5. **Use KMS customer-managed keys** for encryption with audited key rotation.
6. **Set a recovery window** on deletion (7+ days) to avoid accidental permanent loss.
7. **Audit with CloudTrail** — monitor `GetSecretValue` calls to detect exfiltration.
8. **Version secrets** — Secrets Manager versions secrets automatically; use `VersionStage` when needed.

## Common Errors

| Error | Cause | Fix |
|-------|-------|-----|
| `ResourceNotFoundException` | Secret name/ARN wrong | Verify `SECRETS_MANAGER_SECRET` |
| `AccessDeniedException` | IAM lacks `GetSecretValue` | Update IAM policy |
| `InvalidParameterException` | Malformed secret string | Ensure valid JSON |
| Secret contains recovery window | Deleted but in recovery | Wait for recovery to finish |
| Decryption failure | KMS key missing/disabled | Check KMS key permissions |

---

← Back to [Docs Index](README.md) · Next: [Lambda Guide](lambda-guide.md)
