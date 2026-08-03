"""Secrets Manager service for secure secret storage."""

import json
from contextlib import asynccontextmanager
from typing import Any

import aioboto3
from botocore.exceptions import ClientError

from app.core.config import settings
from app.core.logging import get_logger

logger = get_logger(__name__)


class SecretsManagerService:
    """Service for interacting with AWS Secrets Manager."""

    def __init__(self):
        self.session = aioboto3.Session(
            aws_access_key_id=settings.AWS_ACCESS_KEY_ID,
            aws_secret_access_key=settings.AWS_SECRET_ACCESS_KEY,
            region_name=settings.AWS_REGION,
        )
        self._client = None

    @asynccontextmanager
    async def get_client(self):
        """Get Secrets Manager client context manager."""
        async with self.session.client(
            "secretsmanager",
            endpoint_url=settings.AWS_ENDPOINT_URL,
        ) as client:
            yield client

    async def create_secret(
        self,
        name: str,
        secret_value: dict[str, Any],
        description: str | None = None,
        tags: list | None = None,
    ) -> str | None:
        """Create a new secret."""
        try:
            async with self.get_client() as client:
                response = await client.create_secret(
                    Name=name,
                    SecretString=json.dumps(secret_value),
                    Description=description,
                    Tags=tags or [],
                )
            arn = response["ARN"]
            logger.info("Secret created", name=name, arn=arn)
            return arn
        except ClientError as e:
            if e.response["Error"]["Code"] == "ResourceExistsException":
                logger.info("Secret already exists", name=name)
                return await self.update_secret(name, secret_value)
            logger.error("Failed to create secret", name=name, error=str(e))
            return None

    async def get_secret(self, name: str) -> dict[str, Any] | None:
        """Get a secret value."""
        try:
            async with self.get_client() as client:
                response = await client.get_secret_value(SecretId=name)

            secret_string = response.get("SecretString")
            if secret_string:
                return json.loads(secret_string)
            return None
        except ClientError as e:
            if e.response["Error"]["Code"] == "ResourceNotFoundException":
                logger.warning("Secret not found", name=name)
                return None
            logger.error("Failed to get secret", name=name, error=str(e))
            return None

    async def update_secret(
        self,
        name: str,
        secret_value: dict[str, Any],
    ) -> str | None:
        """Update an existing secret."""
        try:
            async with self.get_client() as client:
                response = await client.put_secret_value(
                    SecretId=name,
                    SecretString=json.dumps(secret_value),
                )
            arn = response["ARN"]
            logger.info("Secret updated", name=name, arn=arn)
            return arn
        except ClientError as e:
            logger.error("Failed to update secret", name=name, error=str(e))
            return None

    async def delete_secret(
        self,
        name: str,
        recovery_window_days: int = 7,
    ) -> bool:
        """Delete a secret."""
        try:
            async with self.get_client() as client:
                await client.delete_secret(
                    SecretId=name,
                    RecoveryWindowInDays=recovery_window_days,
                )
            logger.info("Secret deleted", name=name)
            return True
        except ClientError as e:
            logger.error("Failed to delete secret", name=name, error=str(e))
            return False

    async def list_secrets(self, max_results: int = 100) -> list:
        """List secrets."""
        try:
            async with self.get_client() as client:
                response = await client.list_secrets(MaxResults=max_results)
            return response.get("SecretList", [])
        except ClientError as e:
            logger.error("Failed to list secrets", error=str(e))
            return []

    async def rotate_secret(self, name: str) -> bool:
        """Trigger secret rotation."""
        try:
            async with self.get_client() as client:
                await client.rotate_secret(SecretId=name)
            logger.info("Secret rotation triggered", name=name)
            return True
        except ClientError as e:
            logger.error("Failed to rotate secret", name=name, error=str(e))
            return False


# Global Secrets Manager service instance
secrets_manager_service = SecretsManagerService()
