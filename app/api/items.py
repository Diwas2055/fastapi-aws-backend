"""Items API routes."""

from datetime import UTC, datetime, timedelta
from uuid import UUID

from fastapi import APIRouter, Depends, File, HTTPException, Query, UploadFile, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.logging import get_logger
from app.core.security import get_current_user
from app.db.session import get_db
from app.models import User
from app.schemas import (
    ItemCreate,
    ItemResponse,
    ItemUpdate,
    ItemWithPresignedUrl,
    PaginatedResponse,
    S3UploadRequest,
    S3UploadResponse,
)
from app.services import ItemService
from app.services.aws import s3_service

router = APIRouter()
logger = get_logger(__name__)


@router.post("", response_model=ItemResponse, status_code=status.HTTP_201_CREATED)
async def create_item(
    item_data: ItemCreate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Create a new item."""
    service = ItemService(db)
    return await service.create_item(item_data, current_user.id)


@router.get("", response_model=PaginatedResponse[ItemResponse])
async def list_items(
    page: int = Query(1, ge=1),
    size: int = Query(20, ge=1, le=100),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """List items for current user."""
    service = ItemService(db)
    items, total = await service.get_items(owner_id=current_user.id, page=page, size=size)

    pages = (total + size - 1) // size

    return {
        "items": items,
        "total": total,
        "page": page,
        "size": size,
        "pages": pages,
    }


@router.get("/{item_id}", response_model=ItemResponse)
async def get_item(
    item_id: UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Get item by ID."""
    service = ItemService(db)
    item = await service.get_item(item_id)

    if not item:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Item not found",
        )

    # Check ownership
    if item.owner_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not authorized to access this item",
        )

    return item


@router.get("/{item_id}/download", response_model=ItemWithPresignedUrl)
async def get_item_with_download_url(
    item_id: UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Get item with presigned download URL if file exists."""
    service = ItemService(db)
    item = await service.get_item(item_id)

    if not item:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Item not found",
        )

    if item.owner_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not authorized to access this item",
        )

    presigned_url = None
    if item.s3_key:
        presigned_url = await s3_service.generate_presigned_download_url(item.s3_key)

    return ItemWithPresignedUrl(
        **item.__dict__,
        presigned_url=presigned_url,
    )


@router.put("/{item_id}", response_model=ItemResponse)
async def update_item(
    item_id: UUID,
    item_data: ItemUpdate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Update item."""
    service = ItemService(db)
    item = await service.get_item(item_id)

    if not item:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Item not found",
        )

    if item.owner_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not authorized to update this item",
        )

    return await service.update_item(item_id, item_data)


@router.delete("/{item_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_item(
    item_id: UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Delete item."""
    service = ItemService(db)
    item = await service.get_item(item_id)

    if not item:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Item not found",
        )

    if item.owner_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not authorized to delete this item",
        )

    # Delete from S3 if exists
    if item.s3_key:
        await s3_service.delete_file(item.s3_key)

    await service.delete_item(item_id)


@router.post("/{item_id}/upload-url", response_model=S3UploadResponse)
async def get_upload_url(
    item_id: UUID,
    upload_request: S3UploadRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Get presigned URL for uploading a file to an item."""
    service = ItemService(db)
    item = await service.get_item(item_id)

    if not item:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Item not found",
        )

    if item.owner_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not authorized to upload to this item",
        )

    # Check file size
    if upload_request.file_size > s3_service.settings.S3_MAX_FILE_SIZE:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=(
                f"File size exceeds maximum allowed "
                f"({s3_service.settings.S3_MAX_FILE_SIZE} bytes)"
            ),
        )

    # Generate unique key
    key = s3_service.generate_unique_key(upload_request.filename, f"items/{item_id}")

    # Generate presigned URL
    upload_url = await s3_service.generate_presigned_upload_url(
        key=key,
        content_type=upload_request.content_type,
    )

    # Update item with S3 key
    item.s3_key = key
    await db.commit()

    expires_at = datetime.now(UTC) + timedelta(seconds=s3_service.settings.S3_PRESIGNED_URL_EXPIRY)

    return {
        "upload_url": upload_url,
        "key": key,
        "bucket": s3_service.bucket_name,
        "expires_at": expires_at,
    }


@router.post("/upload", response_model=S3UploadResponse)
async def upload_file_direct(
    file: UploadFile = File(...),
    current_user: User = Depends(get_current_user),
):
    """Direct file upload (for small files)."""
    # Check file size
    content = await file.read()
    if len(content) > s3_service.settings.S3_MAX_FILE_SIZE:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=(
                f"File size exceeds maximum allowed "
                f"({s3_service.settings.S3_MAX_FILE_SIZE} bytes)"
            ),
        )

    # Generate unique key
    filename = file.filename or "upload.bin"
    key = s3_service.generate_unique_key(filename, f"uploads/{current_user.id}")

    # Upload to S3
    from io import BytesIO

    file_obj = BytesIO(content)
    await s3_service.upload_file(
        file_obj=file_obj,
        key=key,
        content_type=file.content_type or "application/octet-stream",
        metadata={"uploaded_by": str(current_user.id)},
    )

    expires_at = datetime.now(UTC) + timedelta(seconds=s3_service.settings.S3_PRESIGNED_URL_EXPIRY)

    return {
        "upload_url": "",  # Not needed for direct upload
        "key": key,
        "bucket": s3_service.bucket_name,
        "expires_at": expires_at,
    }
