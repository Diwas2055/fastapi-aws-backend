"""Main FastAPI application."""

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.trustedhost import TrustedHostMiddleware
from fastapi.responses import JSONResponse
from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor

from app.api import auth, aws, health, items, users
from app.core.config import settings
from app.core.logging import configure_logging, get_logger
from app.db.session import close_db, engine, init_db
from app.services import shutdown_opentelemetry
from app.services.aws_init_service import initialize_aws_services

# Configure logging
configure_logging()
logger = get_logger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan events."""
    # Startup
    logger.info(
        "Starting application", version=settings.APP_VERSION, environment=settings.ENVIRONMENT
    )

    # Initialize database
    await init_db()
    logger.info("Database initialized")

    # Initialize AWS services (create buckets, tables, queues, topics)
    if settings.ENVIRONMENT != "production":
        await initialize_aws_services()

    # Initialize SigNoz observability
    from app.services.signoz_service import setup_opentelemetry
    setup_opentelemetry(engine=engine)

    yield

    # Shutdown
    logger.info("Shutting down application")
    shutdown_opentelemetry()
    await close_db()
    logger.info("Database connections closed")


# Create FastAPI app
app = FastAPI(
    title=settings.APP_NAME,
    version=settings.APP_VERSION,
    description="FastAPI backend with AWS integrations",
    docs_url="/docs" if settings.DEBUG else None,
    redoc_url="/redoc" if settings.DEBUG else None,
    openapi_url="/openapi.json" if settings.DEBUG else None,
    lifespan=lifespan,
)

# Initialize SigNoz observability before app starts
if settings.SIGNOZ_ENABLED:
    FastAPIInstrumentor.instrument_app(app)
    get_logger(__name__).info("SigNoz FastAPI instrumentation enabled")

# Add middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=settings.CORS_ALLOW_CREDENTIALS,
    allow_methods=settings.CORS_ALLOW_METHODS,
    allow_headers=settings.CORS_ALLOW_HEADERS,
)

if not settings.DEBUG:
    app.add_middleware(
        TrustedHostMiddleware,
        allowed_hosts=["*"],  # Configure for production
    )


# Global exception handler
@app.exception_handler(Exception)
async def global_exception_handler(request, exc):
    logger.exception("Unhandled exception", path=request.url.path, error=str(exc))
    return JSONResponse(
        status_code=500,
        content={"detail": "Internal server error"},
    )


# Include routers
app.include_router(health.router, prefix="", tags=["Health"])
app.include_router(auth.router, prefix=f"{settings.API_V1_PREFIX}/auth", tags=["Authentication"])
app.include_router(users.router, prefix=f"{settings.API_V1_PREFIX}/users", tags=["Users"])
app.include_router(items.router, prefix=f"{settings.API_V1_PREFIX}/items", tags=["Items"])
app.include_router(aws.router, prefix=f"{settings.API_V1_PREFIX}/aws", tags=["AWS Services"])


# Root endpoint
@app.get("/")
async def root():
    return {
        "name": settings.APP_NAME,
        "version": settings.APP_VERSION,
        "environment": settings.ENVIRONMENT,
        "docs": "/docs" if settings.DEBUG else "disabled",
    }


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "app.main:app",
        host=settings.HOST,
        port=settings.PORT,
        reload=settings.DEBUG,
        workers=settings.WORKERS if not settings.DEBUG else 1,
    )
