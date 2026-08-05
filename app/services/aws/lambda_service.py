"""Lambda service for enterprise serverless function management."""

import json
import base64
import hashlib
from contextlib import asynccontextmanager
from typing import Any, BinaryIO
from datetime import datetime
from io import BytesIO
import zipfile

import aioboto3
from botocore.exceptions import ClientError
from pydantic import BaseModel

from app.core.config import settings
from app.core.logging import get_logger

logger = get_logger(__name__)


class LambdaFunctionConfig(BaseModel):
    """Configuration for creating/updating a Lambda function."""

    function_name: str
    runtime: str = "python3.12"
    handler: str = "lambda_function.handler"
    role: str | None = None
    description: str | None = None
    timeout: int = 30
    memory_size: int = 128
    publish: bool = False
    environment: dict[str, str] | None = None
    tags: dict[str, str] | None = None
    dead_letter_config: dict[str, str] | None = None
    kms_key_arn: str | None = None
    layers: list[str] | None = None
    tracing_config: dict[str, str] | None = None
    revision_id: str | None = None


class LambdaInvokeRequest(BaseModel):
    """Request model for Lambda invocation."""

    function_name: str
    payload: dict[str, Any]
    invocation_type: str = "RequestResponse"
    log_type: str = "Tail"
    context: dict[str, Any] | None = None


class LambdaLayerConfig(BaseModel):
    """Configuration for publishing a Lambda layer."""

    layer_name: str
    description: str | None = None
    content: bytes
    license_info: str = "MIT"
    compatible_runtimes: list[str] | None = None
    compatible_architectures: list[str] | None = None


class EventSourceMappingConfig(BaseModel):
    """Configuration for Lambda event source mapping."""

    event_source_arn: str
    function_name: str
    starting_position: str = "LATEST"
    batch_size: int = 100
    maximum_batching_window_in_seconds: int = 0
    enabled: bool = True
    filter_criteria: dict[str, Any] | None = None


class LambdaCodeSigningConfig(BaseModel):
    """Configuration for Lambda code signing."""

    function_name: str
    description: str
    allowed_publishers: dict[str, list[str]]
    signing_profiles: list[str] | None = None


class LambdaService:
    """Enterprise-grade service for interacting with AWS Lambda."""

    def __init__(self):
        self.session = aioboto3.Session(
            aws_access_key_id=settings.AWS_ACCESS_KEY_ID,
            aws_secret_access_key=settings.AWS_SECRET_ACCESS_KEY,
            region_name=settings.AWS_REGION,
        )
        self.default_function_name = settings.LAMBDA_FUNCTION_NAME
        self._client = None

    @asynccontextmanager
    async def get_client(self):
        """Get Lambda client context manager."""
        async with self.session.client(
            "lambda",
            endpoint_url=settings.AWS_ENDPOINT_URL,
        ) as client:
            yield client

    def _build_default_role(self, function_name: str) -> str:
        """Build a default IAM role ARN for development/LocalStack."""
        if settings.AWS_ENDPOINT_URL:
            # LocalStack accepts dummy ARNs
            return f"arn:aws:iam::000000000000:role/{function_name}-role"
        return f"arn:aws:iam::{settings.AWS_ACCOUNT_ID or '123456789012'}:role/lambda-execution-role"

    def _build_zip_package(self, code: str | bytes, filename: str = "lambda_function.py") -> bytes:
        """Build a ZIP deployment package from source code."""
        if isinstance(code, str):
            code = code.encode("utf-8")

        zip_buffer = BytesIO()
        with zipfile.ZipFile(zip_buffer, "w", zipfile.ZIP_DEFLATED) as zipf:
            zipf.writestr(filename, code)
        return zip_buffer.getvalue()

    def _build_layer_zip(self, python_libs: list[str] | None = None, node_modules: list[str] | None = None) -> bytes:
        """Build a Lambda layer ZIP package."""
        zip_buffer = BytesIO()
        with zipfile.ZipFile(zip_buffer, "w", zipfile.ZIP_DEFLATED) as zipf:
            if python_libs:
                for lib in python_libs:
                    zipf.writestr(f"python/{lib}", b"")
            if node_modules:
                for mod in node_modules:
                    zipf.writestr(f"nodejs/{mod}", b"")
        return zip_buffer.getvalue()

    def _compute_zip_hash(self, zip_bytes: bytes) -> str:
        """Compute SHA256 hash of ZIP package."""
        return base64.b64encode(hashlib.sha256(zip_bytes).digest()).decode()

    # ──────────────────────────────────────────────────────────────────────────────
    # Function CRUD
    # ──────────────────────────────────────────────────────────────────────────────

    async def create_function(
        self,
        function_name: str,
        runtime: str = "python3.12",
        role: str | None = None,
        handler: str = "lambda_function.handler",
        code: str | bytes | dict[str, Any] | None = None,
        description: str | None = None,
        timeout: int = 30,
        memory_size: int = 128,
        publish: bool = False,
        environment: dict[str, str] | None = None,
        tags: dict[str, str] | None = None,
        dead_letter_config: dict[str, str] | None = None,
        kms_key_arn: str | None = None,
        layers: list[str] | None = None,
        tracing_config: dict[str, str] | None = None,
    ) -> dict[str, Any] | None:
        """Create a new Lambda function.

        Args:
            function_name: Name of the function
            runtime: Lambda runtime (e.g., python3.12, nodejs20.x)
            role: IAM role ARN. Defaults to a dev/LocalStack role if not provided.
            handler: Function handler entry point
            code: Source code (str/bytes) or dict with S3Bucket/S3Key or ZipFile
            description: Function description
            timeout: Timeout in seconds (max 900)
            memory_size: Memory in MB (128-10240)
            publish: Whether to publish a version immediately
            environment: Environment variables
            tags: Resource tags
            dead_letter_config: DLQ config with TargetArn
            kms_key_arn: KMS key for encryption
            layers: List of layer version ARNs
            tracing_config: Tracing mode (Active/PassThrough)
        """
        if not role:
            role = self._build_default_role(function_name)

        # Build code parameter
        if code is None:
            code = {"ZipFile": self._build_zip_package("def handler(event, context):\n    return {'statusCode': 200, 'body': 'ok'}\n")}
        elif isinstance(code, str):
            code = {"ZipFile": self._build_zip_package(code)}
        elif isinstance(code, bytes):
            code = {"ZipFile": code}
        elif isinstance(code, dict):
            code = code

        try:
            params: dict[str, Any] = {
                "FunctionName": function_name,
                "Runtime": runtime,
                "Role": role,
                "Handler": handler,
                "Code": code,
                "Timeout": min(max(timeout, 1), 900),
                "MemorySize": min(max(memory_size, 128), 10240),
                "Publish": publish,
            }

            if description:
                params["Description"] = description
            if environment:
                params["Environment"] = {"Variables": environment}
            if tags:
                params["Tags"] = tags
            if dead_letter_config:
                params["DeadLetterConfig"] = dead_letter_config
            if kms_key_arn:
                params["KMSKeyArn"] = kms_key_arn
            if layers:
                params["Layers"] = layers
            if tracing_config:
                params["TracingConfig"] = tracing_config

            async with self.get_client() as client:
                response = await client.create_function(**params)

            arn = response["FunctionArn"]
            logger.info(
                "Lambda function created",
                function_name=function_name,
                arn=arn,
                runtime=runtime,
                timeout=timeout,
                memory_size=memory_size,
            )
            return response

        except ClientError as e:
            error_code = e.response.get("Error", {}).get("Code", "")
            if error_code == "ResourceConflictException":
                logger.warning("Lambda function already exists", function_name=function_name)
                return await self.get_function(function_name)
            logger.error("Failed to create Lambda function", function_name=function_name, error=str(e))
            return None

    async def get_function(self, function_name: str, qualifier: str | None = None) -> dict[str, Any] | None:
        """Get Lambda function configuration and code location."""
        try:
            async with self.get_client() as client:
                params: dict[str, Any] = {"FunctionName": function_name}
                if qualifier:
                    params["Qualifier"] = qualifier
                response = await client.get_function(**params)
            return response
        except ClientError as e:
            logger.error("Failed to get Lambda function", function_name=function_name, error=str(e))
            return None

    async def list_functions(self, max_items: int = 50, marker: str | None = None) -> dict[str, Any]:
        """List Lambda functions."""
        try:
            async with self.get_client() as client:
                params: dict[str, Any] = {"MaxItems": max_items}
                if marker:
                    params["Marker"] = marker
                response = await client.list_functions(**params)
            return response
        except ClientError as e:
            logger.error("Failed to list Lambda functions", error=str(e))
            return {"Functions": [], "NextMarker": None}

    async def delete_function(self, function_name: str, qualifier: str | None = None) -> bool:
        """Delete a Lambda function or specific version/alias."""
        try:
            async with self.get_client() as client:
                params: dict[str, Any] = {"FunctionName": function_name}
                if qualifier:
                    params["Qualifier"] = qualifier
                await client.delete_function(**params)
            logger.info("Lambda function deleted", function_name=function_name, qualifier=qualifier)
            return True
        except ClientError as e:
            logger.error("Failed to delete Lambda function", function_name=function_name, error=str(e))
            return False

    async def update_function_code(
        self,
        function_name: str,
        zip_file: bytes | None = None,
        s3_bucket: str | None = None,
        s3_key: str | None = None,
        s3_object_version: str | None = None,
        publish: bool = False,
    ) -> dict[str, Any] | None:
        """Update Lambda function code.

        Provide either zip_file bytes or S3 location.
        """
        try:
            code: dict[str, Any] = {}
            if zip_file is not None:
                code["ZipFile"] = zip_file
            elif s3_bucket and s3_key:
                code["S3Bucket"] = s3_bucket
                code["S3Key"] = s3_key
                if s3_object_version:
                    code["S3ObjectVersion"] = s3_object_version
            else:
                logger.error("Must provide zip_file or S3 location")
                return None

            async with self.get_client() as client:
                response = await client.update_function_code(
                    FunctionName=function_name,
                    Publish=publish,
                    **code,
                )
            logger.info("Lambda function code updated", function_name=function_name)
            return response
        except ClientError as e:
            logger.error("Failed to update Lambda code", function_name=function_name, error=str(e))
            return None

    async def update_function_configuration(
        self,
        function_name: str,
        runtime: str | None = None,
        role: str | None = None,
        handler: str | None = None,
        description: str | None = None,
        timeout: int | None = None,
        memory_size: int | None = None,
        environment: dict[str, str] | None = None,
        dead_letter_config: dict[str, str] | None = None,
        kms_key_arn: str | None = None,
        layers: list[str] | None = None,
        tracing_config: dict[str, str] | None = None,
        revision_id: str | None = None,
    ) -> dict[str, Any] | None:
        """Update Lambda function configuration."""
        try:
            params: dict[str, Any] = {"FunctionName": function_name}
            updates = {
                "Runtime": runtime,
                "Role": role,
                "Handler": handler,
                "Description": description,
                "Timeout": timeout,
                "MemorySize": memory_size,
                "Environment": {"Variables": environment} if environment else None,
                "DeadLetterConfig": dead_letter_config,
                "KMSKeyArn": kms_key_arn,
                "Layers": layers,
                "TracingConfig": tracing_config,
                "RevisionId": revision_id,
            }

            for key, value in updates.items():
                if value is not None:
                    params[key] = value

            async with self.get_client() as client:
                response = await client.update_function_configuration(**params)
            logger.info("Lambda function configuration updated", function_name=function_name)
            return response
        except ClientError as e:
            logger.error("Failed to update Lambda config", function_name=function_name, error=str(e))
            return None

    # ──────────────────────────────────────────────────────────────────────────────
    # Versions
    # ──────────────────────────────────────────────────────────────────────────────

    async def publish_version(
        self,
        function_name: str,
        description: str | None = None,
        revision_id: str | None = None,
    ) -> dict[str, Any] | None:
        """Publish a new Lambda function version."""
        try:
            async with self.get_client() as client:
                params: dict[str, Any] = {"FunctionName": function_name}
                if description:
                    params["Description"] = description
                if revision_id:
                    params["RevisionId"] = revision_id
                response = await client.publish_version(**params)
            logger.info("Lambda version published", function_name=function_name, version=response.get("Version"))
            return response
        except ClientError as e:
            logger.error("Failed to publish Lambda version", function_name=function_name, error=str(e))
            return None

    async def list_versions_by_function(self, function_name: str, max_items: int = 50) -> dict[str, Any]:
        """List all versions of a Lambda function."""
        try:
            async with self.get_client() as client:
                response = await client.list_versions_by_function(
                    FunctionName=function_name,
                    MaxItems=max_items,
                )
            return response
        except ClientError as e:
            logger.error("Failed to list Lambda versions", function_name=function_name, error=str(e))
            return {"Versions": []}

    # ──────────────────────────────────────────────────────────────────────────────
    # Aliases
    # ──────────────────────────────────────────────────────────────────────────────

    async def create_alias(
        self,
        function_name: str,
        name: str,
        function_version: str = "$LATEST",
        description: str | None = None,
        routing_config: dict[str, Any] | None = None,
    ) -> dict[str, Any] | None:
        """Create a Lambda alias (e.g., prod, staging)."""
        try:
            async with self.get_client() as client:
                params: dict[str, Any] = {
                    "FunctionName": function_name,
                    "Name": name,
                    "FunctionVersion": function_version,
                }
                if description:
                    params["Description"] = description
                if routing_config:
                    params["RoutingConfig"] = routing_config
                response = await client.create_alias(**params)
            logger.info("Lambda alias created", function_name=function_name, alias=name)
            return response
        except ClientError as e:
            logger.error("Failed to create Lambda alias", function_name=function_name, alias=name, error=str(e))
            return None

    async def update_alias(
        self,
        function_name: str,
        name: str,
        function_version: str | None = None,
        description: str | None = None,
        routing_config: dict[str, Any] | None = None,
    ) -> dict[str, Any] | None:
        """Update an existing Lambda alias."""
        try:
            async with self.get_client() as client:
                params: dict[str, Any] = {"FunctionName": function_name, "Name": name}
                if function_version:
                    params["FunctionVersion"] = function_version
                if description:
                    params["Description"] = description
                if routing_config:
                    params["RoutingConfig"] = routing_config
                response = await client.update_alias(**params)
            logger.info("Lambda alias updated", function_name=function_name, alias=name)
            return response
        except ClientError as e:
            logger.error("Failed to update Lambda alias", function_name=function_name, alias=name, error=str(e))
            return None

    async def delete_alias(self, function_name: str, name: str) -> bool:
        """Delete a Lambda alias."""
        try:
            async with self.get_client() as client:
                await client.delete_alias(FunctionName=function_name, Name=name)
            logger.info("Lambda alias deleted", function_name=function_name, alias=name)
            return True
        except ClientError as e:
            logger.error("Failed to delete Lambda alias", function_name=function_name, alias=name, error=str(e))
            return False

    async def list_aliases(self, function_name: str, max_items: int = 50) -> dict[str, Any]:
        """List all aliases for a Lambda function."""
        try:
            async with self.get_client() as client:
                response = await client.list_aliases(
                    FunctionName=function_name,
                    MaxItems=max_items,
                )
            return response
        except ClientError as e:
            logger.error("Failed to list Lambda aliases", function_name=function_name, error=str(e))
            return {"Aliases": []}

    # ──────────────────────────────────────────────────────────────────────────────
    # Invocation
    # ──────────────────────────────────────────────────────────────────────────────

    async def invoke(
        self,
        payload: dict[str, Any],
        function_name: str | None = None,
        invocation_type: str = "RequestResponse",
        log_type: str = "Tail",
        client_context: str | None = None,
        qualifier: str | None = None,
    ) -> dict[str, Any] | None:
        """Invoke a Lambda function.

        Args:
            payload: Event payload dict
            function_name: Function name or ARN
            invocation_type: RequestResponse, Event, or DryRun
            log_type: Tail or None
            client_context: Base64-encoded client context
            qualifier: Version or alias to invoke
        """
        function = function_name or self.default_function_name
        if not function:
            logger.error("No function name configured for Lambda invocation")
            return None

        try:
            async with self.get_client() as client:
                params: dict[str, Any] = {
                    "FunctionName": function,
                    "InvocationType": invocation_type,
                    "LogType": log_type,
                    "Payload": json.dumps(payload),
                }
                if client_context:
                    params["ClientContext"] = client_context
                if qualifier:
                    params["Qualifier"] = qualifier

                response = await client.invoke(**params)

            result = {
                "status_code": response["StatusCode"],
                "payload": None,
                "log_result": response.get("LogResult"),
                "function_error": response.get("FunctionError"),
                "executed_version": response.get("ExecutedVersion"),
                "request_id": response.get("ResponseMetadata", {}).get("RequestId"),
            }

            if "Payload" in response:
                payload_bytes = await response["Payload"].read()
                if payload_bytes:
                    try:
                        result["payload"] = json.loads(payload_bytes)
                    except json.JSONDecodeError:
                        result["payload"] = base64.b64encode(payload_bytes).decode()

            logger.debug(
                "Lambda invoked",
                function=function,
                status=result["status_code"],
                invocation_type=invocation_type,
            )
            return result

        except ClientError as e:
            logger.error("Failed to invoke Lambda", function=function, error=str(e))
            return None

    async def invoke_async(
        self,
        payload: dict[str, Any],
        function_name: str | None = None,
        qualifier: str | None = None,
    ) -> dict[str, Any] | None:
        """Invoke Lambda asynchronously (Event invocation type)."""
        return await self.invoke(
            payload=payload,
            function_name=function_name,
            invocation_type="Event",
            qualifier=qualifier,
        )

    async def invoke_with_retry(
        self,
        payload: dict[str, Any],
        function_name: str | None = None,
        max_retries: int = 3,
        retry_delay: float = 1.0,
        **kwargs,
    ) -> dict[str, Any] | None:
        """Invoke Lambda with exponential backoff retry."""
        import asyncio

        function = function_name or self.default_function_name
        last_error = None

        for attempt in range(max_retries):
            result = await self.invoke(payload=payload, function_name=function_name, **kwargs)
            if result and result.get("status_code") in (200, 202, 204):
                return result
            if result and result.get("function_error"):
                logger.warning(
                    "Lambda invocation returned error",
                    function=function,
                    attempt=attempt + 1,
                    error=result.get("function_error"),
                )
            last_error = result
            await asyncio.sleep(retry_delay * (2**attempt))

        logger.error("Lambda invocation failed after retries", function=function, max_retries=max_retries)
        return last_error

    # ──────────────────────────────────────────────────────────────────────────────
    # Event Source Mappings
    # ──────────────────────────────────────────────────────────────────────────────

    async def create_event_source_mapping(
        self,
        event_source_arn: str,
        function_name: str,
        starting_position: str = "LATEST",
        batch_size: int = 100,
        maximum_batching_window_in_seconds: int = 0,
        enabled: bool = True,
        filter_criteria: dict[str, Any] | None = None,
        maximum_retry_attempts: int = 3,
        parallelization_factor: int = 1,
    ) -> dict[str, Any] | None:
        """Create event source mapping between AWS service and Lambda."""
        try:
            async with self.get_client() as client:
                params: dict[str, Any] = {
                    "EventSourceArn": event_source_arn,
                    "FunctionName": function_name,
                    "StartingPosition": starting_position,
                    "BatchSize": min(max(batch_size, 1), 10000),
                    "Enabled": enabled,
                    "MaximumRetryAttempts": max_retry_attempts,
                    "ParallelizationFactor": min(max(parallelization_factor, 1), 10),
                }
                if maximum_batching_window_in_seconds > 0:
                    params["MaximumBatchingWindowInSeconds"] = maximum_batching_window_in_seconds
                if filter_criteria:
                    params["FilterCriteria"] = filter_criteria

                response = await client.create_event_source_mapping(**params)
            logger.info(
                "Event source mapping created",
                function=function_name,
                source=event_source_arn,
                uuid=response.get("UUID"),
            )
            return response
        except ClientError as e:
            logger.error("Failed to create event source mapping", function=function_name, error=str(e))
            return None

    async def list_event_source_mappings(
        self,
        function_name: str | None = None,
        event_source_arn: str | None = None,
        max_items: int = 50,
    ) -> dict[str, Any]:
        """List event source mappings."""
        try:
            async with self.get_client() as client:
                params: dict[str, Any] = {"MaxItems": max_items}
                if function_name:
                    params["FunctionName"] = function_name
                if event_source_arn:
                    params["EventSourceArn"] = event_source_arn
                response = await client.list_event_source_mappings(**params)
            return response
        except ClientError as e:
            logger.error("Failed to list event source mappings", error=str(e))
            return {"EventSourceMappings": []}

    async def delete_event_source_mapping(self, uuid: str) -> bool:
        """Delete an event source mapping by UUID."""
        try:
            async with self.get_client() as client:
                await client.delete_event_source_mapping(UUID=uuid)
            logger.info("Event source mapping deleted", uuid=uuid)
            return True
        except ClientError as e:
            logger.error("Failed to delete event source mapping", uuid=uuid, error=str(e))
            return False

    async def get_event_source_mapping(self, uuid: str) -> dict[str, Any] | None:
        """Get event source mapping details."""
        try:
            async with self.get_client() as client:
                response = await client.get_event_source_mapping(UUID=uuid)
            return response
        except ClientError as e:
            logger.error("Failed to get event source mapping", uuid=uuid, error=str(e))
            return None

    # ──────────────────────────────────────────────────────────────────────────────
    # Layers
    # ──────────────────────────────────────────────────────────────────────────────

    async def publish_layer_version(
        self,
        layer_name: str,
        content: bytes,
        description: str | None = None,
        license_info: str = "MIT",
        compatible_runtimes: list[str] | None = None,
        compatible_architectures: list[str] | None = None,
    ) -> dict[str, Any] | None:
        """Publish a new Lambda layer version."""
        try:
            async with self.get_client() as client:
                params: dict[str, Any] = {
                    "LayerName": layer_name,
                    "Content": {"ZipFile": content},
                    "LicenseInfo": license_info,
                }
                if description:
                    params["Description"] = description
                if compatible_runtimes:
                    params["CompatibleRuntimes"] = compatible_runtimes
                if compatible_architectures:
                    params["CompatibleArchitectures"] = compatible_architectures

                response = await client.publish_layer_version(**params)
            logger.info("Lambda layer published", layer_name=layer_name, version=response.get("Version"))
            return response
        except ClientError as e:
            logger.error("Failed to publish Lambda layer", layer_name=layer_name, error=str(e))
            return None

    async def list_layers(self, max_items: int = 50) -> dict[str, Any]:
        """List Lambda layers."""
        try:
            async with self.get_client() as client:
                response = await client.list_layers(MaxItems=max_items)
            return response
        except ClientError as e:
            logger.error("Failed to list Lambda layers", error=str(e))
            return {"Layers": []}

    async def get_layer_version(self, layer_name: str, version_number: int) -> dict[str, Any] | None:
        """Get a specific layer version."""
        try:
            async with self.get_client() as client:
                response = await client.get_layer_version(
                    LayerName=layer_name,
                    VersionNumber=version_number,
                )
            return response
        except ClientError as e:
            logger.error("Failed to get Lambda layer version", layer_name=layer_name, version=version_number, error=str(e))
            return None

    # ──────────────────────────────────────────────────────────────────────────────
    # Tags
    # ──────────────────────────────────────────────────────────────────────────────

    async def tag_resource(self, resource_arn: str, tags: dict[str, str]) -> bool:
        """Tag a Lambda function or layer."""
        try:
            async with self.get_client() as client:
                await client.tag_resource(Resource=resource_arn, Tags=tags)
            logger.info("Lambda resource tagged", arn=resource_arn, tags=list(tags.keys()))
            return True
        except ClientError as e:
            logger.error("Failed to tag Lambda resource", arn=resource_arn, error=str(e))
            return False

    async def untag_resource(self, resource_arn: str, tag_keys: list[str]) -> bool:
        """Remove tags from a Lambda function or layer."""
        try:
            async with self.get_client() as client:
                await client.untag_resource(Resource=resource_arn, TagKeys=tag_keys)
            logger.info("Lambda resource untagged", arn=resource_arn, keys=tag_keys)
            return True
        except ClientError as e:
            logger.error("Failed to untag Lambda resource", arn=resource_arn, error=str(e))
            return False

    # ──────────────────────────────────────────────────────────────────────────────
    # Permissions / Resource Policy
    # ──────────────────────────────────────────────────────────────────────────────

    async def add_permission(
        self,
        function_name: str,
        statement_id: str,
        action: str,
        principal: str,
        source_arn: str | None = None,
        source_account: str | None = None,
        qualifier: str | None = None,
    ) -> dict[str, Any] | None:
        """Add a permission statement to the function's resource policy."""
        try:
            async with self.get_client() as client:
                params: dict[str, Any] = {
                    "FunctionName": function_name,
                    "StatementId": statement_id,
                    "Action": action,
                    "Principal": principal,
                }
                if source_arn:
                    params["SourceArn"] = source_arn
                if source_account:
                    params["SourceAccount"] = source_account
                if qualifier:
                    params["Qualifier"] = qualifier

                response = await client.add_permission(**params)
            logger.info("Lambda permission added", function=function_name, statement=statement_id)
            return response
        except ClientError as e:
            logger.error("Failed to add Lambda permission", function=function_name, error=str(e))
            return None

    async def remove_permission(self, function_name: str, statement_id: str, qualifier: str | None = None) -> bool:
        """Remove a permission statement from the function's resource policy."""
        try:
            async with self.get_client() as client:
                params: dict[str, Any] = {"FunctionName": function_name, "StatementId": statement_id}
                if qualifier:
                    params["Qualifier"] = qualifier
                await client.remove_permission(**params)
            logger.info("Lambda permission removed", function=function_name, statement=statement_id)
            return True
        except ClientError as e:
            logger.error("Failed to remove Lambda permission", function=function_name, error=str(e))
            return False

    async def get_policy(self, function_name: str, qualifier: str | None = None) -> dict[str, Any] | None:
        """Get the resource policy for a Lambda function."""
        try:
            async with self.get_client() as client:
                params: dict[str, Any] = {"FunctionName": function_name}
                if qualifier:
                    params["Qualifier"] = qualifier
                response = await client.get_policy(**params)
            return response
        except ClientError as e:
            logger.error("Failed to get Lambda policy", function=function_name, error=str(e))
            return None

    # ──────────────────────────────────────────────────────────────────────────────
    # Code Signing
    # ──────────────────────────────────────────────────────────────────────────────

    async def create_code_signing_config(
        self,
        description: str,
        allowed_publishers: dict[str, list[str]],
        signing_profiles: list[str] | None = None,
    ) -> dict[str, Any] | None:
        """Create a code signing configuration."""
        try:
            async with self.get_client() as client:
                params: dict[str, Any] = {
                    "Description": description,
                    "AllowedPublishers": allowed_publishers,
                }
                if signing_profiles:
                    params["SigningProfiles"] = signing_profiles
                response = await client.create_code_signing_config(**params)
            logger.info("Code signing config created", config_id=response.get("CodeSigningConfigId"))
            return response
        except ClientError as e:
            logger.error("Failed to create code signing config", error=str(e))
            return None

    async def get_code_signing_config(self, code_signing_config_arn: str) -> dict[str, Any] | None:
        """Get code signing configuration."""
        try:
            async with self.get_client() as client:
                response = await client.get_code_signing_config(CodeSigningConfigArn=code_signing_config_arn)
            return response
        except ClientError as e:
            logger.error("Failed to get code signing config", arn=code_signing_config_arn, error=str(e))
            return None

    # ──────────────────────────────────────────────────────────────────────────────
    # Concurrency
    # ──────────────────────────────────────────────────────────────────────────────

    async def put_function_concurrency(
        self,
        function_name: str,
        reserved_concurrent_executions: int,
    ) -> dict[str, Any] | None:
        """Set reserved concurrency for a function."""
        try:
            async with self.get_client() as client:
                response = await client.put_function_concurrency(
                    FunctionName=function_name,
                    ReservedConcurrentExecutions=reserved_concurrent_executions,
                )
            logger.info(
                "Lambda concurrency set",
                function=function_name,
                reserved=reserved_concurrent_executions,
            )
            return response
        except ClientError as e:
            logger.error("Failed to set Lambda concurrency", function=function_name, error=str(e))
            return None

    async def delete_function_concurrency(self, function_name: str) -> bool:
        """Remove reserved concurrency from a function."""
        try:
            async with self.get_client() as client:
                await client.delete_function_concurrency(FunctionName=function_name)
            logger.info("Lambda concurrency removed", function=function_name)
            return True
        except ClientError as e:
            logger.error("Failed to delete Lambda concurrency", function=function_name, error=str(e))
            return False


# Global Lambda service instance
lambda_service = LambdaService()
