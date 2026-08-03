"""
AWS services package.
"""
from app.services.aws.s3_service import s3_service
from app.services.aws.dynamodb_service import dynamodb_service
from app.services.aws.sqs_service import sqs_service
from app.services.aws.sns_service import sns_service
from app.services.aws.secrets_service import secrets_manager_service
from app.services.aws.lambda_service import lambda_service
from app.services.aws.cloudwatch_service import cloudwatch_service

__all__ = [
    "s3_service",
    "dynamodb_service",
    "sqs_service",
    "sns_service",
    "secrets_manager_service",
    "lambda_service",
    "cloudwatch_service",
]