"""
Core configuration module for the FastAPI application.
Handles environment variables, settings, and application configuration.
"""
from functools import lru_cache
from typing import Optional
from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import Field, PostgresDsn, RedisDsn, AnyUrl
import secrets


class Settings(BaseSettings):
    """Application settings with environment variable support."""
    
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=True,
        extra="ignore"
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
    
    # Redis
    REDIS_URL: RedisDsn = Field(default="redis://localhost:6379/0")
    REDIS_MAX_CONNECTIONS: int = 50
    REDIS_SOCKET_TIMEOUT: int = 5
    REDIS_SOCKET_CONNECT_TIMEOUT: int = 5
    
    # AWS Configuration
    AWS_REGION: str = "us-east-1"
    AWS_ACCESS_KEY_ID: Optional[str] = None
    AWS_SECRET_ACCESS_KEY: Optional[str] = None
    AWS_ENDPOINT_URL: Optional[str] = None  # For LocalStack
    AWS_SESSION_TOKEN: Optional[str] = None
    
    # S3
    S3_BUCKET: str = "fastapi-uploads"
    S3_PRESIGNED_URL_EXPIRY: int = 3600
    S3_MAX_FILE_SIZE: int = 10 * 1024 * 1024  # 10MB
    
    # DynamoDB
    DYNAMODB_TABLE: str = "fastapi-items"
    DYNAMODB_ENDPOINT_URL: Optional[str] = None
    
    # SQS
    SQS_QUEUE_URL: Optional[str] = None
    SQS_VISIBILITY_TIMEOUT: int = 300
    SQS_MAX_RECEIVE_COUNT: int = 3
    
    # SNS
    SNS_TOPIC_ARN: Optional[str] = None
    
    # Secrets Manager
    SECRETS_MANAGER_SECRET: Optional[str] = None
    
    # Lambda
    LAMBDA_FUNCTION_NAME: Optional[str] = None
    
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
    
    # Email (optional)
    SMTP_HOST: Optional[str] = None
    SMTP_PORT: int = 587
    SMTP_USER: Optional[str] = None
    SMTP_PASSWORD: Optional[str] = None
    EMAIL_FROM: Optional[str] = None
    
    # Celery
    CELERY_BROKER_URL: Optional[str] = None
    CELERY_RESULT_BACKEND: Optional[str] = None
    
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