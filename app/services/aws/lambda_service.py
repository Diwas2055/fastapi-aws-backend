"""Lambda service for serverless function invocations."""

import json
from contextlib import asynccontextmanager
from typing import Any

import aioboto3
from botocore.exceptions import ClientError

from app.core.config import settings
from app.core.logging import get_logger

logger = get_logger(__name__)


class LambdaService:
    """Service for interacting with AWS Lambda."""

    def __init__(self):
        self.session = aioboto3.Session(
            aws_access_key_id=settings.AWS_ACCESS_KEY_ID,
            aws_secret_access_key=settings.AWS_SECRET_ACCESS_KEY,
            region_name=settings.AWS_REGION,
        )
        self.function_name = settings.LAMBDA_FUNCTION_NAME
        self._client = None

    @asynccontextmanager
    async def get_client(self):
        """Get Lambda client context manager."""
        async with self.session.client(
            "lambda",
            endpoint_url=settings.AWS_ENDPOINT_URL,
        ) as client:
            yield client

    async def invoke(
        self,
        payload: dict[str, Any],
        function_name: str | None = None,
        invocation_type: str = "RequestResponse",  # RequestResponse, Event, DryRun
        log_type: str = "Tail",
    ) -> dict[str, Any] | None:
        """Invoke a Lambda function."""
        function = function_name or self.function_name
        if not function:
            logger.error("No function name configured")
            return None

        try:
            async with self.get_client() as client:
                response = await client.invoke(
                    FunctionName=function,
                    InvocationType=invocation_type,
                    LogType=log_type,
                    Payload=json.dumps(payload),
                )

            result = {
                "status_code": response["StatusCode"],
                "payload": None,
                "log_result": response.get("LogResult"),
                "function_error": response.get("FunctionError"),
            }

            if "Payload" in response:
                payload_bytes = await response["Payload"].read()
                result["payload"] = json.loads(payload_bytes) if payload_bytes else None

            logger.debug("Lambda invoked", function=function, status=result["status_code"])
            return result

        except ClientError as e:
            logger.error("Failed to invoke Lambda", function=function, error=str(e))
            return None

    async def invoke_async(
        self,
        payload: dict[str, Any],
        function_name: str | None = None,
    ) -> bool:
        """Invoke a Lambda function asynchronously."""
        result = await self.invoke(
            payload=payload,
            function_name=function_name,
            invocation_type="Event",
        )
        return result is not None and result["status_code"] == 202

    async def create_function(
        self,
        function_name: str,
        runtime: str,
        role: str,
        handler: str,
        code: dict[str, Any],
        description: str | None = None,
        timeout: int = 30,
        memory_size: int = 128,
        environment: dict[str, str] | None = None,
    ) -> str | None:
        """Create a Lambda function (requires deployment package)."""
        try:
            async with self.get_client() as client:
                params = {
                    "FunctionName": function_name,
                    "Runtime": runtime,
                    "Role": role,
                    "Handler": handler,
                    "Code": code,
                    "Timeout": timeout,
                    "MemorySize": memory_size,
                }

                if description:
                    params["Description"] = description
                if environment:
                    params["Environment"] = {"Variables": environment}

                response = await client.create_function(**params)

            arn = response["FunctionArn"]
            logger.info("Lambda function created", name=function_name, arn=arn)
            return arn

        except ClientError as e:
            logger.error("Failed to create Lambda function", error=str(e))
            return None

    async def update_function_code(
        self,
        function_name: str,
        zip_file: bytes,
    ) -> bool:
        """Update Lambda function code."""
        try:
            async with self.get_client() as client:
                await client.update_function_code(
                    FunctionName=function_name,
                    ZipFile=zip_file,
                )
            logger.info("Lambda function code updated", name=function_name)
            return True
        except ClientError as e:
            logger.error("Failed to update Lambda code", error=str(e))
            return False

    async def update_function_configuration(
        self,
        function_name: str,
        **kwargs,
    ) -> bool:
        """Update Lambda function configuration."""
        try:
            async with self.get_client() as client:
                await client.update_function_configuration(
                    FunctionName=function_name,
                    **kwargs,
                )
            logger.info("Lambda function configuration updated", name=function_name)
            return True
        except ClientError as e:
            logger.error("Failed to update Lambda config", error=str(e))
            return False

    async def delete_function(self, function_name: str) -> bool:
        """Delete a Lambda function."""
        try:
            async with self.get_client() as client:
                await client.delete_function(FunctionName=function_name)
            logger.info("Lambda function deleted", name=function_name)
            return True
        except ClientError as e:
            logger.error("Failed to delete Lambda function", error=str(e))
            return False

    async def get_function(self, function_name: str) -> dict[str, Any] | None:
        """Get Lambda function configuration."""
        try:
            async with self.get_client() as client:
                response = await client.get_function(FunctionName=function_name)
            return response.get("Configuration")
        except ClientError as e:
            logger.error("Failed to get Lambda function", error=str(e))
            return None


# Global Lambda service instance
lambda_service = LambdaService()
