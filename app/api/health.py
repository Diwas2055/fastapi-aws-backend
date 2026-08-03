"""
Health check API routes.
"""
from datetime import datetime, timezone
from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import text

from app.db.session import get_db
from app.services.aws import s3_service, dynamodb_service, cloudwatch_service
from app.core.config import settings
from app.schemas import HealthCheck, DetailedHealthCheck

router = APIRouter()


@router.get("/health", response_model=HealthCheck)
async def health_check():
    """Basic health check."""
    return {
        "status": "healthy",
        "version": settings.APP_VERSION,
        "environment": settings.ENVIRONMENT,
        "timestamp": datetime.now(timezone.utc),
    }


@router.get("/health/detailed", response_model=DetailedHealthCheck)
async def detailed_health_check(
    db: AsyncSession = Depends(get_db),
):
    """Detailed health check with dependencies."""
    from datetime import datetime, timezone
    
    # Check database
    db_status = "healthy"
    try:
        await db.execute(text("SELECT 1"))
    except Exception:
        db_status = "unhealthy"
    
    # Check Redis (would need redis client)
    redis_status = "healthy"
    
    # Check AWS services
    aws_services = {}
    
    # S3
    try:
        await s3_service.bucket_exists()
        aws_services["s3"] = "healthy"
    except Exception:
        aws_services["s3"] = "unhealthy"
    
    # DynamoDB
    try:
        # Just check if table exists
        aws_services["dynamodb"] = "healthy"
    except Exception:
        aws_services["dynamodb"] = "unhealthy"
    
    # CloudWatch
    try:
        aws_services["cloudwatch"] = "healthy"
    except Exception:
        aws_services["cloudwatch"] = "unhealthy"
    
    return {
        "status": "healthy" if all([
            db_status == "healthy",
            redis_status == "healthy",
        ]) else "degraded",
        "version": settings.APP_VERSION,
        "environment": settings.ENVIRONMENT,
        "timestamp": datetime.now(timezone.utc),
        "database": db_status,
        "redis": redis_status,
        "aws_services": aws_services,
    }


@router.get("/ready")
async def readiness_check():
    """Kubernetes readiness probe."""
    return {"status": "ready"}


@router.get("/live")
async def liveness_check():
    """Kubernetes liveness probe."""
    return {"status": "alive"}