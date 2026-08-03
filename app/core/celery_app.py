"""Celery configuration for background tasks."""

import os

from celery import Celery

from app.core.config import settings

# Build Celery URL
celery_broker_url = os.getenv("CELERY_BROKER_URL", settings.REDIS_URL)
celery_result_backend = os.getenv("CELERY_RESULT_BACKEND", settings.REDIS_URL)

# Create Celery app
celery_app = Celery(
    "fastapi-worker",
    broker=celery_broker_url,
    backend=celery_result_backend,
    include=[
        "app.services.tasks.email_tasks",
        "app.services.tasks.aws_tasks",
        "app.services.tasks.maintenance_tasks",
    ],
)

# Celery configuration
celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="UTC",
    enable_utc=True,
    task_track_started=True,
    task_time_limit=300,
    task_soft_time_limit=240,
    worker_prefetch_multiplier=4,
    worker_max_tasks_per_child=100,
    result_expires=3600,
    task_acks_late=True,
    task_reject_on_worker_lost=True,
    task_default_retry_delay=60,
    task_max_retries=3,
)

# Optional: Beat schedule for periodic tasks
celery_app.conf.beat_schedule = {
    "cleanup-expired-refresh-tokens": {
        "task": "app.services.tasks.maintenance_tasks.cleanup_expired_refresh_tokens",
        "schedule": 86400.0,  # Every 24 hours
    },
    "cleanup-temp-files": {
        "task": "app.services.tasks.maintenance_tasks.cleanup_temp_files",
        "schedule": 3600.0,  # Every hour
    },
}


if __name__ == "__main__":
    celery_app.start()
