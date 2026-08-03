"""Maintenance background tasks."""

from datetime import UTC, datetime, timedelta
from typing import Any

from celery import shared_task
from sqlalchemy import delete

from app.core.logging import get_logger
from app.db.session import async_session_maker
from app.models import RefreshToken

logger = get_logger(__name__)


@shared_task(bind=True, max_retries=2)
def cleanup_expired_refresh_tokens(self) -> dict[str, Any]:
    """Clean up expired and revoked refresh tokens."""
    try:
        logger.info("Starting cleanup of expired refresh tokens")

        # We need to run this in an async context
        import asyncio

        result = asyncio.run(_cleanup_refresh_tokens())

        logger.info("Cleanup completed", **result)
        return result
    except Exception as exc:
        logger.error("Failed to cleanup refresh tokens", error=str(exc))
        raise self.retry(exc=exc, countdown=300)


async def _cleanup_refresh_tokens() -> dict[str, Any]:
    """Async function to clean up refresh tokens."""
    async with async_session_maker() as db:
        # Delete expired tokens
        expired_stmt = delete(RefreshToken).where(RefreshToken.expires_at < datetime.now(UTC))
        expired_result = await db.execute(expired_stmt)
        expired_count = expired_result.rowcount

        # Delete revoked tokens older than 7 days
        revoked_cutoff = datetime.now(UTC) - timedelta(days=7)
        revoked_stmt = delete(RefreshToken).where(
            RefreshToken.revoked.is_(True),
            RefreshToken.created_at < revoked_cutoff,
        )
        revoked_result = await db.execute(revoked_stmt)
        revoked_count = revoked_result.rowcount

        await db.commit()

        return {
            "expired_deleted": expired_count,
            "revoked_deleted": revoked_count,
        }


@shared_task(bind=True, max_retries=2)
def cleanup_temp_files(self) -> dict[str, Any]:
    """Clean up temporary files."""
    try:
        logger.info("Starting cleanup of temporary files")

        # TODO: Implement actual temp file cleanup
        # - Clean up /tmp files older than 24 hours
        # - Clean up S3 multipart uploads
        # - Clean up local temp directories

        logger.info("Temp file cleanup completed")
        return {"status": "completed"}
    except Exception as exc:
        logger.error("Failed to cleanup temp files", error=str(exc))
        raise self.retry(exc=exc, countdown=300)


@shared_task(bind=True, max_retries=1)
def database_maintenance_task(self) -> dict[str, Any]:
    """Run database maintenance tasks."""
    try:
        logger.info("Starting database maintenance")

        # TODO: Implement actual maintenance
        # - VACUUM ANALYZE (PostgreSQL)
        # - Update table statistics
        # - Check for index bloat

        logger.info("Database maintenance completed")
        return {"status": "completed"}
    except Exception as exc:
        logger.error("Failed database maintenance", error=str(exc))
        raise self.retry(exc=exc, countdown=600)
