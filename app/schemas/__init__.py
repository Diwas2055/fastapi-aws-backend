"""
Pydantic schemas for request/response validation.
"""
from datetime import datetime
from typing import Optional, List, Any
from pydantic import BaseModel, EmailStr, Field, ConfigDict
import uuid


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
    full_name: Optional[str] = Field(None, max_length=255)


class UserCreate(UserBase):
    password: str = Field(..., min_length=8, max_length=128)


class UserUpdate(BaseSchema):
    email: Optional[EmailStr] = None
    full_name: Optional[str] = Field(None, max_length=255)
    is_active: Optional[bool] = None


class UserResponse(UserBase):
    id: uuid.UUID
    is_active: bool
    is_superuser: bool
    created_at: datetime
    updated_at: datetime
    last_login: Optional[datetime] = None


class UserInDB(UserResponse):
    hashed_password: str


# Token schemas
class Token(BaseSchema):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"


class TokenData(BaseSchema):
    sub: Optional[str] = None
    exp: Optional[int] = None
    type: str = "access"


class RefreshTokenCreate(BaseSchema):
    token: str
    expires_at: datetime
    user_agent: Optional[str] = None
    ip_address: Optional[str] = None


class RefreshTokenResponse(BaseSchema):
    id: uuid.UUID
    expires_at: datetime
    revoked: bool
    created_at: datetime
    user_agent: Optional[str] = None


# Item schemas
class ItemBase(BaseSchema):
    title: str = Field(..., min_length=1, max_length=255)
    description: Optional[str] = None
    is_public: bool = False


class ItemCreate(ItemBase):
    pass


class ItemUpdate(BaseSchema):
    title: Optional[str] = Field(None, min_length=1, max_length=255)
    description: Optional[str] = None
    is_public: Optional[bool] = None


class ItemResponse(ItemBase):
    id: uuid.UUID
    owner_id: uuid.UUID
    s3_key: Optional[str] = None
    dynamodb_id: Optional[str] = None
    created_at: datetime
    updated_at: datetime


class ItemWithPresignedUrl(ItemResponse):
    presigned_url: Optional[str] = None


# Pagination schemas
class PageParams(BaseSchema):
    page: int = Field(1, ge=1)
    size: int = Field(20, ge=1, le=100)


class PageResponse(BaseSchema):
    total: int
    page: int
    size: int
    pages: int


class PaginatedResponse(BaseSchema, PageResponse):
    items: List[Any]


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
    field: Optional[str] = None
    message: str
    code: str


class ErrorResponse(BaseSchema):
    detail: str
    errors: Optional[List[ErrorDetail]] = None


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
    message_attributes: Optional[dict] = None


class SQSMessageResponse(BaseSchema):
    message_id: str
    md5_of_body: str
    sequence_number: Optional[str] = None


class SNSMessagePublish(BaseSchema):
    message: str
    subject: Optional[str] = None
    message_attributes: Optional[dict] = None


class SNSMessageResponse(BaseSchema):
    message_id: str
    sequence_number: Optional[str] = None


# Audit log schemas
class AuditLogResponse(BaseSchema):
    id: uuid.UUID
    user_id: Optional[uuid.UUID] = None
    action: str
    resource_type: str
    resource_id: Optional[str] = None
    details: Optional[str] = None
    ip_address: Optional[str] = None
    user_agent: Optional[str] = None
    created_at: datetime


# Bulk operations
class BulkDeleteRequest(BaseSchema):
    ids: List[uuid.UUID] = Field(..., min_length=1, max_length=100)


class BulkOperationResponse(BaseSchema):
    success_count: int
    failed_count: int
    errors: List[ErrorDetail] = []