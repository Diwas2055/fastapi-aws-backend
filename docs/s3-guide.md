# S3 — File Storage with Presigned URLs

## What It Is

Amazon Simple Storage Service (S3) is AWS's object storage service. It stores any amount of data (files, images, videos, backups, static assets) as objects inside buckets. It is designed for 99.999999999% durability (11 nines).

## Why We Use It

In this FastAPI backend, S3 is the primary file storage layer:
- Upload and store user files (images, documents, uploads) referenced by Items
- Generate presigned URLs so browsers/clients upload/download directly to S3 without exposing AWS credentials
- Store static assets with metadata (uploader, content-type, timestamps)
- Enable direct-to-S3 uploads that bypass the application server entirely (scales, cheap)

## How It Works

### Architecture

```
Client ──(presigned PUT URL)──▶ S3 Bucket (fastapi-uploads)
   │
   ├── POST /items/{id}/upload-url  ──▶ app ── generates presigned URL
   ├── POST /items/upload           ──▶ app ── streams file to S3
   └── GET  /items/{id}/download    ──▶ app ── presigned GET URL
```

### Configuration

```python
# app/core/config.py
S3_BUCKET: str = "fastapi-uploads"
S3_PRESIGNED_URL_EXPIRY: int = 3600        # 1 hour
S3_MAX_FILE_SIZE: int = 10 * 1024 * 1024   # 10 MB
```

| Config | Default | Purpose |
|--------|---------|---------|
| `S3_BUCKET` | `fastapi-uploads` | Bucket name |
| `S3_PRESIGNED_URL_EXPIRY` | `3600` | Seconds a presigned URL stays valid |
| `S3_MAX_FILE_SIZE` | `10 MB` | Upload size limit (checked before upload) |
| `AWS_REGION` | `us-east-1` | Bucket region |
| `AWS_ENDPOINT_URL` | `http://localhost:4566` | LocalStack endpoint for dev |

### Service Class

```python
# app/services/aws/s3_service.py
class S3Service:
    async def create_bucket(bucket_name=None) -> bool
    async def bucket_exists(bucket_name=None) -> bool
    async def generate_presigned_upload_url(key, content_type, expires_in=None) -> str
    async def generate_presigned_download_url(key, expires_in=None) -> str
    async def upload_file(file_obj, key, content_type, metadata=None) -> dict
    async def download_file(key) -> bytes
    async def delete_file(key) -> bool
    async def delete_files(keys) -> dict
    async def list_files(prefix="", max_keys=1000) -> list
    async def get_file_metadata(key) -> dict | None
    async def copy_file(source_key, dest_key, source_bucket=None) -> bool
    def generate_unique_key(filename, prefix="") -> str
```

Uses aioboto3 (async AWS SDK) with `s3_service = S3Service()` as the global instance.

## Code Usage Examples

### 1. Generate a presigned upload URL

```python
from app.services.aws import s3_service

key = s3_service.generate_unique_key("report.pdf", prefix="items/123")
url = await s3_service.generate_presigned_upload_url(
    key=key,
    content_type="application/pdf",
)
# Client now does: PUT {url} with the file body
```

### 2. Upload a file directly (small files)

```python
from io import BytesIO

content = await file.read()
await s3_service.upload_file(
    file_obj=BytesIO(content),
    key=f"uploads/{user_id}/{filename}",
    content_type=file.content_type,
    metadata={"uploaded_by": str(user_id)},
)
```

### 3. Generate a download URL

```python
url = await s3_service.generate_presigned_download_url(item.s3_key)
# -> https://bucket.s3.amazonaws.com/items/123/abc.pdf?X-Amz-...
```

### 4. Delete files (single / batch)

```python
await s3_service.delete_file(item.s3_key)
await s3_service.delete_files(["a.pdf", "b.pdf", "c.pdf"])
```

## API Endpoints

| Method | Endpoint | Auth | Description |
|--------|----------|------|-------------|
| `POST` | `/api/v1/aws/s3/bucket` | Superuser | Create bucket |
| `GET` | `/api/v1/aws/s3/files?prefix=&max_keys=` | Superuser | List files |
| `GET` | `/api/v1/aws/s3/files/{key}` | Superuser | Get file metadata |
| `DELETE` | `/api/v1/aws/s3/files/{key}` | Superuser | Delete file |
| `POST` | `/api/v1/aws/s3/upload-url` | Superuser | Get presigned upload URL |
| `POST` | `/api/v1/items/{item_id}/upload-url` | User (owner) | Presigned URL for item file |
| `POST` | `/api/v1/items/upload` | User | Direct file upload |
| `GET` | `/api/v1/items/{item_id}/download` | User (owner) | Presigned download URL |

## LocalStack Setup

```bash
# Create bucket
aws --endpoint-url=http://localhost:4566 s3 mb s3://fastapi-uploads --region us-east-1

# List buckets
aws --endpoint-url=http://localhost:4566 s3 ls

# Upload a test file
echo "hello" | aws --endpoint-url=http://localhost:4566 s3 cp - s3://fastapi-uploads/test.txt

# Download
aws --endpoint-url=http://localhost:4566 s3 cp s3://fastapi-uploads/test.txt -
```

## IAM Policy (production)

```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Action": [
        "s3:PutObject",
        "s3:GetObject",
        "s3:DeleteObject",
        "s3:ListBucket"
      ],
      "Resource": [
        "arn:aws:s3:::fastapi-uploads",
        "arn:aws:s3:::fastapi-uploads/*"
      ]
    }
  ]
}
```

## Security Best Practices

1. **Never use long-term keys in the app** — use IAM roles (ECS task roles, EKS IRSA).
2. **Presigned URLs** — short expiry (1 hour), scoped to one object and one action.
3. **Private buckets by default** — never set public-read; use presigned URLs for access.
4. **Validate uploads** — check content-type and size (`S3_MAX_FILE_SIZE`) before upload.
5. **Bucket versioning** — enable for rollback of accidental overwrites/deletes.
6. **Server-side encryption** — enable SSE-S3 or SSE-KMS on the bucket.
7. **Block public access** — enable the "Block Public Access" settings.
8. **Enable CloudTrail** — audit who accessed objects.

## Common Errors

| Error | Cause | Fix |
|-------|-------|-----|
| `BucketAlreadyExists` | Bucket name taken globally | Use a unique name |
| `AccessDenied` | IAM role/permissions missing | Check IAM policy |
| `NoSuchKey` | Object doesn't exist | Verify key path |
| `Presigned URL expired` | URL older than expiry | Generate a new URL |
| `EntityTooLarge` | File exceeds 5GB | Use multipart upload |

---

← Back to [Docs Index](README.md) · Next: [DynamoDB Guide](dynamodb-guide.md)
