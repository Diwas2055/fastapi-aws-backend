"""Pydantic schemas for request/response validation."""

import uuid
from datetime import datetime
from typing import Generic, TypeVar

from pydantic import BaseModel, ConfigDict, EmailStr, Field


# Base schemas
class BaseSchema(BaseModel):
    """Base schema with common configuration."""

    model_config = ConfigDict(
        from_attributes=True,
        populate_by_name=True,
        str_strip_whitespace=True,
    )


# User schemas
class UserBase(BaseSchema):
    email: EmailStr
    full_name: str | None = Field(None, max_length=255)


class UserCreate(UserBase):
    password: str = Field(..., min_length=8, max_length=128)


class UserUpdate(BaseSchema):
    email: EmailStr | None = None
    full_name: str | None = Field(None, max_length=255)
    is_active: bool | None = None


class UserResponse(UserBase):
    id: uuid.UUID
    is_active: bool
    is_superuser: bool
    created_at: datetime
    updated_at: datetime
    last_login: datetime | None = None


class UserInDB(UserResponse):
    hashed_password: str


# Token schemas
class Token(BaseSchema):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"


class TokenData(BaseSchema):
    sub: str | None = None
    exp: int | None = None
    type: str = "access"


class RefreshTokenCreate(BaseSchema):
    token: str
    expires_at: datetime
    user_agent: str | None = None
    ip_address: str | None = None


class RefreshRequest(BaseSchema):
    refresh_token: str


class RefreshTokenResponse(BaseSchema):
    id: uuid.UUID
    expires_at: datetime
    revoked: bool
    created_at: datetime
    user_agent: str | None = None


# Item schemas
class ItemBase(BaseSchema):
    title: str = Field(..., min_length=1, max_length=255)
    description: str | None = None
    is_public: bool = False


class ItemCreate(ItemBase):
    pass


class ItemUpdate(BaseSchema):
    title: str | None = Field(None, min_length=1, max_length=255)
    description: str | None = None
    is_public: bool | None = None


class ItemResponse(ItemBase):
    id: uuid.UUID
    owner_id: uuid.UUID
    s3_key: str | None = None
    dynamodb_id: str | None = None
    created_at: datetime
    updated_at: datetime


class ItemWithPresignedUrl(ItemResponse):
    presigned_url: str | None = None


# Pagination schemas
T = TypeVar("T")


class PageParams(BaseSchema):
    page: int = Field(1, ge=1)
    size: int = Field(20, ge=1, le=100)


class PageResponse(BaseSchema):
    total: int
    page: int
    size: int
    pages: int


class PaginatedResponse(PageResponse, Generic[T]):
    items: list[T]


# Health check schemas
class HealthCheck(BaseSchema):
    status: str
    version: str
    environment: str
    timestamp: datetime


class DetailedHealthCheck(HealthCheck):
    database: str
    redis: str
    aws_services: dict


# Error schemas
class ErrorDetail(BaseSchema):
    field: str | None = None
    message: str
    code: str


class ErrorResponse(BaseSchema):
    detail: str
    errors: list[ErrorDetail] | None = None


# AWS Service schemas
class S3UploadRequest(BaseSchema):
    filename: str = Field(..., min_length=1, max_length=255)
    content_type: str = Field(..., min_length=1)
    file_size: int = Field(..., gt=0)


class S3UploadResponse(BaseSchema):
    upload_url: str
    key: str
    bucket: str
    expires_at: datetime


class S3FileResponse(BaseSchema):
    key: str
    bucket: str
    url: str
    size: int
    content_type: str
    last_modified: datetime


class DynamoDBItemCreate(BaseSchema):
    pk: str
    sk: str
    data: dict


class DynamoDBItemResponse(BaseSchema):
    pk: str
    sk: str
    data: dict
    created_at: datetime


class SQSMessageSend(BaseSchema):
    message_body: dict
    delay_seconds: int = Field(0, ge=0, le=900)
    message_attributes: dict | None = None


class SQSMessageResponse(BaseSchema):
    message_id: str
    md5_of_body: str
    sequence_number: str | None = None


class SNSMessagePublish(BaseSchema):
    message: str
    subject: str | None = None
    message_attributes: dict | None = None


class SNSMessageResponse(BaseSchema):
    message_id: str
    sequence_number: str | None = None


# Audit log schemas
class AuditLogResponse(BaseSchema):
    id: uuid.UUID
    user_id: uuid.UUID | None = None
    action: str
    resource_type: str
    resource_id: str | None = None
    details: str | None = None
    ip_address: str | None = None
    user_agent: str | None = None
    created_at: datetime


# Bulk operations
class BulkDeleteRequest(BaseSchema):
    ids: list[uuid.UUID] = Field(..., min_length=1, max_length=100)


class BulkOperationResponse(BaseSchema):
    success_count: int
    failed_count: int
    errors: list[ErrorDetail] = []
