"""AWS services API routes."""

from datetime import UTC
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel

from app.core.logging import get_logger
from app.core.security import get_current_active_superuser
from app.models import User
from app.services.aws import (
    cloudwatch_service,
    dynamodb_service,
    lambda_service,
    s3_service,
    secrets_manager_service,
    sns_service,
    sqs_service,
)
from app.services.aws.lambda_service import (
    EventSourceMappingConfig,
    LambdaFunctionConfig,
    LambdaInvokeRequest,
    LambdaLayerConfig,
)

router = APIRouter()
logger = get_logger(__name__)


# S3 Routes
@router.post("/s3/bucket", status_code=status.HTTP_201_CREATED)
async def create_s3_bucket(
    bucket_name: str,
    current_user: User = Depends(get_current_active_superuser),
):
    """Create S3 bucket."""
    success = await s3_service.create_bucket(bucket_name)
    if not success:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to create bucket",
        )
    return {"message": "Bucket created", "bucket": bucket_name}


@router.get("/s3/files")
async def list_s3_files(
    prefix: str = "",
    max_keys: int = 100,
    current_user: User = Depends(get_current_active_superuser),
):
    """List files in S3 bucket."""
    files = await s3_service.list_files(prefix=prefix, max_keys=max_keys)
    return {"files": files}


@router.get("/s3/files/{key:path}")
async def get_s3_file(
    key: str,
    current_user: User = Depends(get_current_active_superuser),
):
    """Get file metadata from S3."""
    metadata = await s3_service.get_file_metadata(key)
    if not metadata:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="File not found",
        )
    return metadata


@router.delete("/s3/files/{key:path}")
async def delete_s3_file(
    key: str,
    current_user: User = Depends(get_current_active_superuser),
):
    """Delete file from S3."""
    success = await s3_service.delete_file(key)
    if not success:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to delete file",
        )
    return {"message": "File deleted"}


@router.post("/s3/upload-url")
async def get_s3_upload_url(
    filename: str,
    content_type: str,
    prefix: str = "",
    current_user: User = Depends(get_current_active_superuser),
):
    """Get presigned upload URL."""
    key = s3_service.generate_unique_key(filename, prefix)
    url = await s3_service.generate_presigned_upload_url(key, content_type)

    from datetime import datetime, timedelta

    expires_at = datetime.now(UTC) + timedelta(seconds=s3_service.settings.S3_PRESIGNED_URL_EXPIRY)

    return {
        "upload_url": url,
        "key": key,
        "bucket": s3_service.bucket_name,
        "expires_at": expires_at,
    }


# DynamoDB Routes
class DynamoDBItemRequest(BaseModel):
    pk: str
    sk: str
    data: dict[str, Any]
    gsi1pk: str | None = None
    gsi1sk: str | None = None


class DynamoDBQueryRequest(BaseModel):
    pk: str
    sk_prefix: str | None = None
    limit: int = 100


@router.post("/dynamodb/table", status_code=status.HTTP_201_CREATED)
async def create_dynamodb_table(
    current_user: User = Depends(get_current_active_superuser),
):
    """Create DynamoDB table."""
    success = await dynamodb_service.create_table()
    if not success:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to create table",
        )
    return {"message": "Table created", "table": dynamodb_service.table_name}


@router.post("/dynamodb/items")
async def put_dynamodb_item(
    item: DynamoDBItemRequest,
    current_user: User = Depends(get_current_active_superuser),
):
    """Put item in DynamoDB."""
    success = await dynamodb_service.put_item(
        pk=item.pk,
        sk=item.sk,
        data=item.data,
        gsi1pk=item.gsi1pk,
        gsi1sk=item.gsi1sk,
    )
    if not success:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to put item",
        )
    return {"message": "Item created"}


@router.get("/dynamodb/items/{pk}/{sk}")
async def get_dynamodb_item(
    pk: str,
    sk: str,
    current_user: User = Depends(get_current_active_superuser),
):
    """Get item from DynamoDB."""
    item = await dynamodb_service.get_item(pk, sk)
    if not item:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Item not found",
        )
    return item


@router.post("/dynamodb/query")
async def query_dynamodb(
    query: DynamoDBQueryRequest,
    current_user: User = Depends(get_current_active_superuser),
):
    """Query DynamoDB items."""
    return await dynamodb_service.query_items(
        pk=query.pk,
        sk_prefix=query.sk_prefix,
        limit=query.limit,
    )


# SQS Routes
class SQSMessageRequest(BaseModel):
    message_body: dict[str, Any]
    delay_seconds: int = 0
    message_attributes: dict[str, dict] | None = None


@router.post("/sqs/send")
async def send_sqs_message(
    message: SQSMessageRequest,
    current_user: User = Depends(get_current_active_superuser),
):
    """Send message to SQS queue."""
    result = await sqs_service.send_message(
        message_body=message.message_body,
        delay_seconds=message.delay_seconds,
        message_attributes=message.message_attributes,
    )
    if not result:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to send message",
        )
    return result


@router.post("/sqs/receive")
async def receive_sqs_messages(
    max_messages: int = Query(10, ge=1, le=10),
    wait_time: int = Query(20, ge=0, le=20),
    current_user: User = Depends(get_current_active_superuser),
):
    """Receive messages from SQS queue."""
    messages = await sqs_service.receive_messages(
        max_messages=max_messages,
        wait_time_seconds=wait_time,
    )
    return {"messages": messages}


# SNS Routes
class SNSMessageRequest(BaseModel):
    message: str
    subject: str | None = None
    message_attributes: dict[str, dict] | None = None


@router.post("/sns/publish")
async def publish_sns_message(
    message: SNSMessageRequest,
    current_user: User = Depends(get_current_active_superuser),
):
    """Publish message to SNS topic."""
    result = await sns_service.publish(
        message=message.message,
        subject=message.subject,
        message_attributes=message.message_attributes,
    )
    if not result:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to publish message",
        )
    return result


# Secrets Manager Routes
class SecretRequest(BaseModel):
    name: str
    value: dict[str, Any]
    description: str | None = None


@router.post("/secrets")
async def create_secret(
    secret: SecretRequest,
    current_user: User = Depends(get_current_active_superuser),
):
    """Create a secret."""
    arn = await secrets_manager_service.create_secret(
        name=secret.name,
        secret_value=secret.value,
        description=secret.description,
    )
    if not arn:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to create secret",
        )
    return {"arn": arn}


@router.get("/secrets/{name}")
async def get_secret(
    name: str,
    current_user: User = Depends(get_current_active_superuser),
):
    """Get a secret."""
    value = await secrets_manager_service.get_secret(name)
    if value is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Secret not found",
        )
    return {"value": value}


# Lambda Routes
@router.post("/lambda/invoke")
async def invoke_lambda(
    request: LambdaInvokeRequest,
    current_user: User = Depends(get_current_active_superuser),
):
    """Invoke Lambda function (sync or async)."""
    result = await lambda_service.invoke(
        payload=request.payload,
        function_name=request.function_name,
        invocation_type=request.invocation_type,
        log_type=request.log_type,
    )
    if not result:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to invoke Lambda",
        )
    return result


@router.post("/lambda/invoke-with-retry")
async def invoke_lambda_with_retry(
    function_name: str,
    payload: dict[str, Any],
    max_retries: int = Query(3, ge=1, le=10),
    current_user: User = Depends(get_current_active_superuser),
):
    """Invoke Lambda with exponential backoff retry."""
    result = await lambda_service.invoke_with_retry(
        payload=payload,
        function_name=function_name,
        max_retries=max_retries,
    )
    if not result:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Lambda invocation failed after retries",
        )
    return result


@router.post("/lambda/functions", status_code=status.HTTP_201_CREATED)
async def create_lambda_function(
    config: LambdaFunctionConfig,
    current_user: User = Depends(get_current_active_superuser),
):
    """Create a new Lambda function."""
    result = await lambda_service.create_function(
        function_name=config.function_name,
        runtime=config.runtime,
        role=config.role,
        handler=config.handler,
        code=None,
        description=config.description,
        timeout=config.timeout,
        memory_size=config.memory_size,
        publish=config.publish,
        environment=config.environment,
        tags=config.tags,
        dead_letter_config=config.dead_letter_config,
        kms_key_arn=config.kms_key_arn,
        layers=config.layers,
        tracing_config=config.tracing_config,
    )
    if not result:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to create Lambda function",
        )
    return result


@router.get("/lambda/functions")
async def list_lambda_functions(
    max_items: int = Query(50, ge=1, le=100),
    current_user: User = Depends(get_current_active_superuser),
):
    """List all Lambda functions."""
    result = await lambda_service.list_functions(max_items=max_items)
    return result


@router.get("/lambda/functions/{function_name}")
async def get_lambda_function(
    function_name: str,
    qualifier: str | None = None,
    current_user: User = Depends(get_current_active_superuser),
):
    """Get Lambda function details."""
    result = await lambda_service.get_function(function_name, qualifier=qualifier)
    if not result:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Lambda function not found",
        )
    return result


@router.put("/lambda/functions/{function_name}")
async def update_lambda_function(
    function_name: str,
    config: LambdaFunctionConfig,
    current_user: User = Depends(get_current_active_superuser),
):
    """Update Lambda function configuration."""
    result = await lambda_service.update_function_configuration(
        function_name=function_name,
        runtime=config.runtime,
        role=config.role,
        handler=config.handler,
        description=config.description,
        timeout=config.timeout,
        memory_size=config.memory_size,
        environment=config.environment,
        dead_letter_config=config.dead_letter_config,
        kms_key_arn=config.kms_key_arn,
        layers=config.layers,
        tracing_config=config.tracing_config,
    )
    if not result:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to update Lambda function",
        )
    return result


@router.delete("/lambda/functions/{function_name}")
async def delete_lambda_function(
    function_name: str,
    qualifier: str | None = None,
    current_user: User = Depends(get_current_active_superuser),
):
    """Delete a Lambda function."""
    success = await lambda_service.delete_function(function_name, qualifier=qualifier)
    if not success:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to delete Lambda function",
        )
    return {"message": "Function deleted"}


@router.post("/lambda/functions/{function_name}/code")
async def update_lambda_code(
    function_name: str,
    code: str,
    publish: bool = False,
    current_user: User = Depends(get_current_active_superuser),
):
    """Update Lambda function code from inline source code."""
    zip_bytes = lambda_service._build_zip_package(code)
    result = await lambda_service.update_function_code(
        function_name=function_name,
        zip_file=zip_bytes,
        publish=publish,
    )
    if not result:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to update Lambda code",
        )
    return result


@router.post("/lambda/functions/{function_name}/versions")
async def publish_lambda_version(
    function_name: str,
    description: str | None = None,
    current_user: User = Depends(get_current_active_superuser),
):
    """Publish a new Lambda function version."""
    result = await lambda_service.publish_version(function_name, description=description)
    if not result:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to publish Lambda version",
        )
    return result


@router.get("/lambda/functions/{function_name}/versions")
async def list_lambda_versions(
    function_name: str,
    max_items: int = Query(50, ge=1, le=100),
    current_user: User = Depends(get_current_active_superuser),
):
    """List all versions of a Lambda function."""
    result = await lambda_service.list_versions_by_function(function_name, max_items=max_items)
    return result


@router.post("/lambda/functions/{function_name}/aliases", status_code=status.HTTP_201_CREATED)
async def create_lambda_alias(
    function_name: str,
    name: str,
    function_version: str = "$LATEST",
    description: str | None = None,
    routing_config: dict[str, Any] | None = None,
    current_user: User = Depends(get_current_active_superuser),
):
    """Create a Lambda alias (e.g., prod, staging)."""
    result = await lambda_service.create_alias(
        function_name=function_name,
        name=name,
        function_version=function_version,
        description=description,
        routing_config=routing_config,
    )
    if not result:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to create Lambda alias",
        )
    return result


@router.get("/lambda/functions/{function_name}/aliases")
async def list_lambda_aliases(
    function_name: str,
    max_items: int = Query(50, ge=1, le=100),
    current_user: User = Depends(get_current_active_superuser),
):
    """List all aliases for a Lambda function."""
    result = await lambda_service.list_aliases(function_name, max_items=max_items)
    return result


@router.delete("/lambda/functions/{function_name}/aliases/{alias_name}")
async def delete_lambda_alias(
    function_name: str,
    alias_name: str,
    current_user: User = Depends(get_current_active_superuser),
):
    """Delete a Lambda alias."""
    success = await lambda_service.delete_alias(function_name, alias_name)
    if not success:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to delete Lambda alias",
        )
    return {"message": "Alias deleted"}


@router.post("/lambda/functions/{function_name}/event-source-mappings", status_code=status.HTTP_201_CREATED)
async def create_event_source_mapping(
    function_name: str,
    config: EventSourceMappingConfig,
    current_user: User = Depends(get_current_active_superuser),
):
    """Create event source mapping between AWS service and Lambda."""
    result = await lambda_service.create_event_source_mapping(
        event_source_arn=config.event_source_arn,
        function_name=config.function_name or function_name,
        starting_position=config.starting_position,
        batch_size=config.batch_size,
        maximum_batching_window_in_seconds=config.maximum_batching_window_in_seconds,
        enabled=config.enabled,
        filter_criteria=config.filter_criteria,
    )
    if not result:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to create event source mapping",
        )
    return result


@router.get("/lambda/functions/{function_name}/event-source-mappings")
async def list_event_source_mappings(
    function_name: str,
    max_items: int = Query(50, ge=1, le=100),
    current_user: User = Depends(get_current_active_superuser),
):
    """List event source mappings for a Lambda function."""
    result = await lambda_service.list_event_source_mappings(
        function_name=function_name,
        max_items=max_items,
    )
    return result


@router.delete("/lambda/event-source-mappings/{uuid}")
async def delete_event_source_mapping(
    uuid: str,
    current_user: User = Depends(get_current_active_superuser),
):
    """Delete an event source mapping."""
    success = await lambda_service.delete_event_source_mapping(uuid)
    if not success:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to delete event source mapping",
        )
    return {"message": "Event source mapping deleted"}


@router.post("/lambda/layers", status_code=status.HTTP_201_CREATED)
async def publish_lambda_layer(
    layer_name: str,
    code: str,
    description: str | None = None,
    compatible_runtimes: list[str] | None = None,
    current_user: User = Depends(get_current_active_superuser),
):
    """Publish a Lambda layer from inline code."""
    zip_bytes = lambda_service._build_layer_zip(python_libs=[code] if code else None)
    result = await lambda_service.publish_layer_version(
        layer_name=layer_name,
        content=zip_bytes,
        description=description,
        compatible_runtimes=compatible_runtimes,
    )
    if not result:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to publish Lambda layer",
        )
    return result


@router.get("/lambda/layers")
async def list_lambda_layers(
    max_items: int = Query(50, ge=1, le=100),
    current_user: User = Depends(get_current_active_superuser),
):
    """List Lambda layers."""
    result = await lambda_service.list_layers(max_items=max_items)
    return result


@router.post("/lambda/functions/{function_name}/concurrency")
async def set_lambda_concurrency(
    function_name: str,
    reserved_concurrent_executions: int = Query(..., ge=0, le=1000),
    current_user: User = Depends(get_current_active_superuser),
):
    """Set reserved concurrency for a Lambda function."""
    result = await lambda_service.put_function_concurrency(
        function_name=function_name,
        reserved_concurrent_executions=reserved_concurrent_executions,
    )
    if not result:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to set Lambda concurrency",
        )
    return result


@router.delete("/lambda/functions/{function_name}/concurrency")
async def delete_lambda_concurrency(
    function_name: str,
    current_user: User = Depends(get_current_active_superuser),
):
    """Remove reserved concurrency from a Lambda function."""
    success = await lambda_service.delete_function_concurrency(function_name)
    if not success:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to delete Lambda concurrency",
        )
    return {"message": "Concurrency removed"}


@router.post("/lambda/functions/{function_name}/permissions", status_code=status.HTTP_201_CREATED)
async def add_lambda_permission(
    function_name: str,
    statement_id: str,
    action: str,
    principal: str,
    source_arn: str | None = None,
    source_account: str | None = None,
    qualifier: str | None = None,
    current_user: User = Depends(get_current_active_superuser),
):
    """Add permission to Lambda function resource policy."""
    result = await lambda_service.add_permission(
        function_name=function_name,
        statement_id=statement_id,
        action=action,
        principal=principal,
        source_arn=source_arn,
        source_account=source_account,
        qualifier=qualifier,
    )
    if not result:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to add Lambda permission",
        )
    return result


@router.delete("/lambda/functions/{function_name}/permissions/{statement_id}")
async def remove_lambda_permission(
    function_name: str,
    statement_id: str,
    qualifier: str | None = None,
    current_user: User = Depends(get_current_active_superuser),
):
    """Remove permission from Lambda function resource policy."""
    success = await lambda_service.remove_permission(
        function_name=function_name,
        statement_id=statement_id,
        qualifier=qualifier,
    )
    if not success:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to remove Lambda permission",
        )
    return {"message": "Permission removed"}


@router.get("/lambda/functions/{function_name}/policy")
async def get_lambda_policy(
    function_name: str,
    qualifier: str | None = None,
    current_user: User = Depends(get_current_active_superuser),
):
    """Get Lambda function resource policy."""
    result = await lambda_service.get_policy(function_name, qualifier=qualifier)
    if not result:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Lambda policy not found",
        )
    return result


# CloudWatch Routes
class MetricRequest(BaseModel):
    namespace: str
    name: str
    value: float
    unit: str = "Count"
    dimensions: list[dict[str, str]] | None = None


@router.post("/cloudwatch/metric")
async def put_metric(
    metric: MetricRequest,
    current_user: User = Depends(get_current_active_superuser),
):
    """Put custom metric."""
    success = await cloudwatch_service.put_metric(
        namespace=metric.namespace,
        name=metric.name,
        value=metric.value,
        unit=metric.unit,
        dimensions=metric.dimensions,
    )
    if not success:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to put metric",
        )
    return {"message": "Metric sent"}


@router.post("/cloudwatch/log")
async def put_log_event(
    message: str,
    level: str = "INFO",
    current_user: User = Depends(get_current_active_superuser),
):
    """Put log event."""
    success = await cloudwatch_service.put_log_event(
        message=message,
        level=level,
    )
    if not success:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to put log event",
        )
    return {"message": "Log event sent"}


@router.get("/cloudwatch/logs")
async def get_log_events(
    hours: int = Query(1, ge=1, le=168),
    limit: int = Query(100, ge=1, le=1000),
    current_user: User = Depends(get_current_active_superuser),
):
    """Get recent log events."""
    from datetime import datetime, timedelta

    start_time = datetime.now(UTC) - timedelta(hours=hours)
    events = await cloudwatch_service.get_log_events(
        start_time=start_time,
        limit=limit,
    )
    return {"events": events}
