"""
Core configuration module for the FastAPI application.

Handles environment variables, settings, and application configuration.
"""

import secrets
from functools import lru_cache

from pydantic import Field, PostgresDsn, RedisDsn, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings with environment variable support."""

    model_config = SettingsConfigDict(
        env_file=".env", env_file_encoding="utf-8", case_sensitive=True, extra="ignore"
    )

    # Application
    APP_NAME: str = "FastAPI AWS Backend"
    APP_VERSION: str = "1.0.0"
    ENVIRONMENT: str = Field(default="development", pattern="^(development|staging|production)$")
    DEBUG: bool = True
    API_V1_PREFIX: str = "/api/v1"

    # Server
    HOST: str = "0.0.0.0"
    PORT: int = 8000
    WORKERS: int = 4

    # Security
    SECRET_KEY: str = Field(default_factory=lambda: secrets.token_urlsafe(32))
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 30
    REFRESH_TOKEN_EXPIRE_DAYS: int = 7
    PASSWORD_MIN_LENGTH: int = 8

    # Database
    DATABASE_URL: PostgresDsn = Field(
        default="postgresql+asyncpg://postgres:postgres@localhost:5432/fastapi_app"
    )
    DATABASE_POOL_SIZE: int = 10
    DATABASE_MAX_OVERFLOW: int = 20
    DATABASE_POOL_TIMEOUT: int = 30

    # AWS RDS
    RDS_INSTANCE_IDENTIFIER: str | None = None
    RDS_ENDPOINT: str | None = None
    RDS_PORT: int = 5432
    RDS_DB_NAME: str | None = None
    RDS_USERNAME: str | None = None
    RDS_PASSWORD: str | None = None
    RDS_POOL_SIZE: int = 10
    RDS_MAX_OVERFLOW: int = 20
    RDS_POOL_TIMEOUT: int = 30
    RDS_POOL_RECYCLE: int = 1800
    RDS_POOL_PRE_PING: bool = True

    @model_validator(mode="after")
    def _build_database_url_from_rds(self) -> "Settings":
        if self.RDS_ENDPOINT and self.RDS_DB_NAME and self.RDS_USERNAME and self.RDS_PASSWORD:
            self.DATABASE_URL = PostgresDsn(
                f"postgresql+asyncpg://{self.RDS_USERNAME}:{self.RDS_PASSWORD}"
                f"@{self.RDS_ENDPOINT}:{self.RDS_PORT}/{self.RDS_DB_NAME}"
            )
        return self

    @property
    def is_rds(self) -> bool:
        return bool(self.RDS_ENDPOINT and self.RDS_DB_NAME and self.RDS_USERNAME and self.RDS_PASSWORD)

    # Redis
    REDIS_URL: RedisDsn = Field(default="redis://localhost:6379/0")
    REDIS_MAX_CONNECTIONS: int = 50
    REDIS_SOCKET_TIMEOUT: int = 5
    REDIS_SOCKET_CONNECT_TIMEOUT: int = 5

    # AWS Configuration
    AWS_REGION: str = "us-east-1"
    AWS_ACCESS_KEY_ID: str | None = None
    AWS_SECRET_ACCESS_KEY: str | None = None
    AWS_ENDPOINT_URL: str | None = None  # For LocalStack
    AWS_SESSION_TOKEN: str | None = None

    # S3
    S3_BUCKET: str = "fastapi-uploads"
    S3_PRESIGNED_URL_EXPIRY: int = 3600
    S3_MAX_FILE_SIZE: int = 10 * 1024 * 1024  # 10MB
    S3_MULTIPART_THRESHOLD: int = 100 * 1024 * 1024  # 100MB
    S3_MULTIPART_PART_SIZE: int = 50 * 1024 * 1024  # 50MB
    S3_MULTIPART_MAX_CONCURRENCY: int = 4

    # DynamoDB
    DYNAMODB_TABLE: str = "fastapi-items"
    DYNAMODB_ENDPOINT_URL: str | None = None

    # SQS
    SQS_QUEUE_URL: str | None = None
    SQS_VISIBILITY_TIMEOUT: int = 300
    SQS_MAX_RECEIVE_COUNT: int = 3

    # SNS
    SNS_TOPIC_ARN: str | None = None

    # Secrets Manager
    SECRETS_MANAGER_SECRET: str | None = None

    # Lambda
    LAMBDA_FUNCTION_NAME: str | None = None

    # CloudWatch
    CLOUDWATCH_LOG_GROUP: str = "/aws/fastapi/app"
    CLOUDWATCH_LOG_STREAM: str = "application"

    # CORS
    CORS_ORIGINS: list[str] = Field(default=["http://localhost:3000", "http://localhost:8080"])
    CORS_ALLOW_CREDENTIALS: bool = True
    CORS_ALLOW_METHODS: list[str] = Field(default=["*"])
    CORS_ALLOW_HEADERS: list[str] = Field(default=["*"])

    # Rate Limiting
    RATE_LIMIT_REQUESTS: int = 100
    RATE_LIMIT_WINDOW: int = 60  # seconds

    # Logging
    LOG_LEVEL: str = Field(default="INFO", pattern="^(DEBUG|INFO|WARNING|ERROR|CRITICAL)$")
    LOG_FORMAT: str = "json"

    # Monitoring
    ENABLE_METRICS: bool = True
    METRICS_PORT: int = 9090

    # SigNoz / OpenTelemetry
    SIGNOZ_ENABLED: bool = True
    SIGNOZ_OTLP_ENDPOINT: str = "http://localhost:4318"
    SIGNOZ_SERVICE_NAME: str = "fastapi-aws-backend"
    SIGNOZ_SERVICE_VERSION: str = "1.0.0"
    SIGNOZ_DEPLOYMENT_ENVIRONMENT: str = "development"
    SIGNOZ_TRACING_SAMPLE_RATE: float = 1.0
    SIGNOZ_UI_URL: str = "http://localhost:3301"

    # Optional email settings
    SMTP_HOST: str | None = None
    SMTP_PORT: int = 587
    SMTP_USER: str | None = None
    SMTP_PASSWORD: str | None = None
    EMAIL_FROM: str | None = None

    # Celery
    CELERY_BROKER_URL: str | None = None
    CELERY_RESULT_BACKEND: str | None = None

    @property
    def is_development(self) -> bool:
        return self.ENVIRONMENT == "development"

    @property
    def is_production(self) -> bool:
        return self.ENVIRONMENT == "production"

    @property
    def database_url_sync(self) -> str:
        """Get synchronous database URL for Alembic."""
        return str(self.DATABASE_URL).replace("postgresql+asyncpg", "postgresql")


@lru_cache
def get_settings() -> Settings:
    """Get cached settings instance."""
    return Settings()


# Global settings instance
settings = get_settings()
