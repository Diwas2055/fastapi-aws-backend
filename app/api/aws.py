"""
AWS services API routes.
"""
from typing import Dict, Any, List, Optional
from fastapi import APIRouter, Depends, HTTPException, status, Query
from pydantic import BaseModel

from app.services.aws import (
    s3_service,
    dynamodb_service,
    sqs_service,
    sns_service,
    secrets_manager_service,
    lambda_service,
    cloudwatch_service,
)
from app.core.security import get_current_active_superuser
from app.models import User
from app.core.logging import get_logger

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
    
    from datetime import datetime, timezone, timedelta
    expires_at = datetime.now(timezone.utc) + timedelta(seconds=s3_service.settings.S3_PRESIGNED_URL_EXPIRY)
    
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
    data: Dict[str, Any]
    gsi1pk: Optional[str] = None
    gsi1sk: Optional[str] = None


class DynamoDBQueryRequest(BaseModel):
    pk: str
    sk_prefix: Optional[str] = None
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
    result = await dynamodb_service.query_items(
        pk=query.pk,
        sk_prefix=query.sk_prefix,
        limit=query.limit,
    )
    return result


# SQS Routes
class SQSMessageRequest(BaseModel):
    message_body: Dict[str, Any]
    delay_seconds: int = 0
    message_attributes: Optional[Dict[str, Dict]] = None


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
    subject: Optional[str] = None
    message_attributes: Optional[Dict[str, Dict]] = None


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
    value: Dict[str, Any]
    description: Optional[str] = None


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
class LambdaInvokeRequest(BaseModel):
    function_name: str
    payload: Dict[str, Any]
    invocation_type: str = "RequestResponse"


@router.post("/lambda/invoke")
async def invoke_lambda(
    request: LambdaInvokeRequest,
    current_user: User = Depends(get_current_active_superuser),
):
    """Invoke Lambda function."""
    result = await lambda_service.invoke(
        payload=request.payload,
        function_name=request.function_name,
        invocation_type=request.invocation_type,
    )
    if not result:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to invoke Lambda",
        )
    return result


# CloudWatch Routes
class MetricRequest(BaseModel):
    namespace: str
    name: str
    value: float
    unit: str = "Count"
    dimensions: Optional[List[Dict[str, str]]] = None


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
    from datetime import datetime, timezone, timedelta
    
    start_time = datetime.now(timezone.utc) - timedelta(hours=hours)
    events = await cloudwatch_service.get_log_events(
        start_time=start_time,
        limit=limit,
    )
    return {"events": events}