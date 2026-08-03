"""
Tasks package initialization.
"""
from app.services.tasks.email_tasks import (
    send_email_task,
    send_welcome_email_task,
    process_upload_task,
)
from app.services.tasks.aws_tasks import (
    sync_to_dynamodb_task,
    send_notification_task,
    process_queue_messages_task,
    invoke_lambda_task,
)
from app.services.tasks.maintenance_tasks import (
    cleanup_expired_refresh_tokens,
    cleanup_temp_files,
    database_maintenance_task,
)

__all__ = [
    "send_email_task",
    "send_welcome_email_task",
    "process_upload_task",
    "sync_to_dynamodb_task",
    "send_notification_task",
    "process_queue_messages_task",
    "invoke_lambda_task",
    "cleanup_expired_refresh_tokens",
    "cleanup_temp_files",
    "database_maintenance_task",
]