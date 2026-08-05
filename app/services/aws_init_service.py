"""AWS services initialization for development with LocalStack."""

from app.core.config import settings
from app.core.logging import get_logger
from app.services.aws import dynamodb_service, lambda_service, s3_service, sns_service, sqs_service

logger = get_logger(__name__)

DEFAULT_LAMBDA_CODE = """def handler(event, context):
    return {
        'statusCode': 200,
        'body': 'Hello from Lambda!'
    }
"""


async def initialize_aws_services() -> None:
    """Initialize AWS resources needed for development.

    Creates S3 bucket, DynamoDB table, SQS queue, SNS topic,
    and a sample Lambda function if they do not already exist.
    Only runs in non-production environments.
    """
    logger.info("Initializing AWS services for development")

    # S3 bucket
    bucket_created = await s3_service.create_bucket()
    if bucket_created:
        logger.info("S3 bucket ready", bucket=s3_service.bucket_name)

    # DynamoDB table
    table_created = await dynamodb_service.create_table()
    if table_created:
        logger.info("DynamoDB table ready", table=dynamodb_service.table_name)

    # SQS queue
    queue_name = "fastapi-queue"
    queue_url = await sqs_service.create_queue(queue_name)
    if queue_url:
        logger.info("SQS queue ready", queue=queue_name, url=queue_url)

    # SNS topic
    topic_name = "fastapi-notifications"
    topic_arn = await sns_service.create_topic(topic_name)
    if topic_arn:
        logger.info("SNS topic ready", topic=topic_name, arn=topic_arn)

    # Lambda function
    function_name = "fastapi-aws-backend-lambda"
    role = "arn:aws:iam::000000000000:role/lambda-ex"
    existing = await lambda_service.get_function(function_name)
    if existing and existing.get("Configuration"):
        logger.info("Lambda function already exists", function=function_name)
    else:
        created = await lambda_service.create_function(
            function_name=function_name,
            runtime="python3.12",
            role=role,
            handler="lambda_function.handler",
            code=DEFAULT_LAMBDA_CODE,
            description="Sample Lambda function for development",
            timeout=30,
            memory_size=128,
            environment={
                "AWS_ENDPOINT_URL": settings.AWS_ENDPOINT_URL or "http://localhost:4566",
                "AWS_REGION": settings.AWS_REGION,
            },
        )
        if created:
            logger.info("Lambda function ready", function=function_name, arn=created.get("FunctionArn"))

    logger.info("AWS services initialization complete")
