"""
S3 service for file storage operations.
"""
import asyncio
from contextlib import asynccontextmanager
from datetime import datetime, timedelta
from typing import Optional, List, BinaryIO
from uuid import uuid4

import aioboto3
from botocore.exceptions import ClientError, NoCredentialsError

from app.core.config import settings
from app.core.logging import get_logger

logger = get_logger(__name__)


class S3Service:
    """Service for interacting with AWS S3."""
    
    def __init__(self):
        self.session = aioboto3.Session(
            aws_access_key_id=settings.AWS_ACCESS_KEY_ID,
            aws_secret_access_key=settings.AWS_SECRET_ACCESS_KEY,
            region_name=settings.AWS_REGION,
        )
        self.settings = settings
        self.bucket_name = settings.S3_BUCKET
        self._client = None
    
    @asynccontextmanager
    async def get_client(self):
        """Get S3 client context manager."""
        if self._client is None:
            async with self.session.client(
                "s3",
                endpoint_url=settings.AWS_ENDPOINT_URL,
            ) as client:
                yield client
        else:
            yield self._client
    
    async def create_bucket(self, bucket_name: Optional[str] = None) -> bool:
        """Create an S3 bucket."""
        bucket = bucket_name or self.bucket_name
        try:
            async with self.get_client() as client:
                if settings.AWS_REGION == "us-east-1":
                    await client.create_bucket(Bucket=bucket)
                else:
                    await client.create_bucket(
                        Bucket=bucket,
                        CreateBucketConfiguration={
                            "LocationConstraint": settings.AWS_REGION
                        },
                    )
            logger.info("Bucket created", bucket=bucket)
            return True
        except ClientError as e:
            if e.response["Error"]["Code"] == "BucketAlreadyExists":
                logger.info("Bucket already exists", bucket=bucket)
                return True
            logger.error("Failed to create bucket", bucket=bucket, error=str(e))
            return False
    
    async def bucket_exists(self, bucket_name: Optional[str] = None) -> bool:
        """Check if bucket exists."""
        bucket = bucket_name or self.bucket_name
        try:
            async with self.get_client() as client:
                await client.head_bucket(Bucket=bucket)
            return True
        except ClientError:
            return False
    
    async def generate_presigned_upload_url(
        self,
        key: str,
        content_type: str,
        expires_in: Optional[int] = None,
    ) -> str:
        """Generate a presigned URL for uploading a file."""
        expires_in = expires_in or settings.S3_PRESIGNED_URL_EXPIRY
        
        async with self.get_client() as client:
            url = await client.generate_presigned_url(
                "put_object",
                Params={
                    "Bucket": self.bucket_name,
                    "Key": key,
                    "ContentType": content_type,
                },
                ExpiresIn=expires_in,
            )
        return url
    
    async def generate_presigned_download_url(
        self,
        key: str,
        expires_in: Optional[int] = None,
    ) -> str:
        """Generate a presigned URL for downloading a file."""
        expires_in = expires_in or settings.S3_PRESIGNED_URL_EXPIRY
        
        async with self.get_client() as client:
            url = await client.generate_presigned_url(
                "get_object",
                Params={
                    "Bucket": self.bucket_name,
                    "Key": key,
                },
                ExpiresIn=expires_in,
            )
        return url
    
    async def upload_file(
        self,
        file_obj: BinaryIO,
        key: str,
        content_type: str,
        metadata: Optional[dict] = None,
    ) -> dict:
        """Upload a file to S3."""
        async with self.get_client() as client:
            extra_args = {"ContentType": content_type}
            if metadata:
                extra_args["Metadata"] = metadata
            
            await client.upload_fileobj(
                file_obj,
                self.bucket_name,
                key,
                ExtraArgs=extra_args,
            )
        
        logger.info("File uploaded", key=key, bucket=self.bucket_name)
        return {
            "key": key,
            "bucket": self.bucket_name,
            "content_type": content_type,
        }
    
    async def download_file(self, key: str) -> bytes:
        """Download a file from S3."""
        async with self.get_client() as client:
            response = await client.get_object(Bucket=self.bucket_name, Key=key)
            return await response["Body"].read()
    
    async def delete_file(self, key: str) -> bool:
        """Delete a file from S3."""
        try:
            async with self.get_client() as client:
                await client.delete_object(Bucket=self.bucket_name, Key=key)
            logger.info("File deleted", key=key)
            return True
        except ClientError as e:
            logger.error("Failed to delete file", key=key, error=str(e))
            return False
    
    async def delete_files(self, keys: List[str]) -> dict:
        """Delete multiple files from S3."""
        if not keys:
            return {"deleted": 0, "errors": []}
        
        async with self.get_client() as client:
            response = await client.delete_objects(
                Bucket=self.bucket_name,
                Delete={"Objects": [{"Key": k} for k in keys]},
            )
        
        deleted = len(response.get("Deleted", []))
        errors = response.get("Errors", [])
        
        logger.info("Files deleted", deleted=deleted, errors=len(errors))
        return {"deleted": deleted, "errors": errors}
    
    async def list_files(
        self,
        prefix: str = "",
        max_keys: int = 1000,
    ) -> List[dict]:
        """List files in the bucket."""
        async with self.get_client() as client:
            paginator = client.get_paginator("list_objects_v2")
            files = []
            
            async for page in paginator.paginate(
                Bucket=self.bucket_name,
                Prefix=prefix,
                PaginationConfig={"MaxItems": max_keys},
            ):
                for obj in page.get("Contents", []):
                    files.append({
                        "key": obj["Key"],
                        "size": obj["Size"],
                        "last_modified": obj["LastModified"],
                        "etag": obj["ETag"].strip('"'),
                    })
        
        return files
    
    async def get_file_metadata(self, key: str) -> Optional[dict]:
        """Get file metadata."""
        try:
            async with self.get_client() as client:
                response = await client.head_object(Bucket=self.bucket_name, Key=key)
                return {
                    "key": key,
                    "size": response["ContentLength"],
                    "content_type": response.get("ContentType"),
                    "last_modified": response["LastModified"],
                    "etag": response["ETag"].strip('"'),
                    "metadata": response.get("Metadata", {}),
                }
        except ClientError as e:
            if e.response["Error"]["Code"] == "404":
                return None
            raise
    
    async def copy_file(
        self,
        source_key: str,
        dest_key: str,
        source_bucket: Optional[str] = None,
    ) -> bool:
        """Copy a file within S3."""
        try:
            async with self.get_client() as client:
                await client.copy_object(
                    Bucket=self.bucket_name,
                    Key=dest_key,
                    CopySource={
                        "Bucket": source_bucket or self.bucket_name,
                        "Key": source_key,
                    },
                )
            logger.info("File copied", source=source_key, dest=dest_key)
            return True
        except ClientError as e:
            logger.error("Failed to copy file", error=str(e))
            return False
    
    def generate_unique_key(self, filename: str, prefix: str = "") -> str:
        """Generate a unique S3 key for a file."""
        ext = filename.split(".")[-1] if "." in filename else ""
        unique_id = uuid4().hex[:12]
        timestamp = datetime.utcnow().strftime("%Y%m%d")
        
        parts = [p for p in [prefix, timestamp, unique_id] if p]
        key = "/".join(parts)
        
        if ext:
            key = f"{key}.{ext}"
        
        return key


# Global S3 service instance
s3_service = S3Service()