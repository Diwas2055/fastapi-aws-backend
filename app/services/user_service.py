"""
User service for business logic related to users.
"""
from typing import Optional, List
from uuid import UUID
from datetime import datetime, timezone

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func

from app.models import User, Item, RefreshToken
from app.schemas import UserCreate, UserUpdate, ItemCreate, ItemUpdate
from app.core.security import (
    get_password_hash,
    verify_password,
    create_access_token,
    create_refresh_token,
    create_refresh_token_db,
    verify_refresh_token,
    revoke_refresh_token,
    revoke_all_user_refresh_tokens,
)
from app.core.logging import get_logger

logger = get_logger(__name__)


class UserService:
    """Service for user-related operations."""
    
    def __init__(self, db: AsyncSession):
        self.db = db
    
    async def create_user(self, user_data: UserCreate) -> User:
        """Create a new user."""
        hashed_password = get_password_hash(user_data.password)
        
        user = User(
            email=user_data.email,
            hashed_password=hashed_password,
            full_name=user_data.full_name,
        )
        
        self.db.add(user)
        await self.db.commit()
        await self.db.refresh(user)
        
        logger.info("User created", user_id=str(user.id), email=user.email)
        return user
    
    async def get_user_by_id(self, user_id: UUID) -> Optional[User]:
        """Get user by ID."""
        result = await self.db.execute(select(User).where(User.id == user_id))
        return result.scalar_one_or_none()
    
    async def get_user_by_email(self, email: str) -> Optional[User]:
        """Get user by email."""
        result = await self.db.execute(select(User).where(User.email == email))
        return result.scalar_one_or_none()
    
    async def get_users(
        self,
        page: int = 1,
        size: int = 20,
    ) -> tuple[List[User], int]:
        """Get paginated list of users."""
        offset = (page - 1) * size
        
        # Get total count
        count_result = await self.db.execute(select(func.count(User.id)))
        total = count_result.scalar()
        
        # Get users
        result = await self.db.execute(
            select(User)
            .order_by(User.created_at.desc())
            .offset(offset)
            .limit(size)
        )
        users = result.scalars().all()
        
        return list(users), total
    
    async def update_user(
        self,
        user_id: UUID,
        user_data: UserUpdate,
    ) -> Optional[User]:
        """Update user."""
        user = await self.get_user_by_id(user_id)
        if not user:
            return None
        
        if user_data.email is not None:
            # Check if email is already taken
            existing = await self.get_user_by_email(user_data.email)
            if existing and existing.id != user_id:
                raise ValueError("Email already registered")
            user.email = user_data.email
        
        if user_data.full_name is not None:
            user.full_name = user_data.full_name
        
        if user_data.is_active is not None:
            user.is_active = user_data.is_active
        
        user.updated_at = datetime.now(timezone.utc)
        
        await self.db.commit()
        await self.db.refresh(user)
        
        logger.info("User updated", user_id=str(user_id))
        return user
    
    async def delete_user(self, user_id: UUID) -> bool:
        """Delete user."""
        user = await self.get_user_by_id(user_id)
        if not user:
            return False
        
        await self.db.delete(user)
        await self.db.commit()
        
        logger.info("User deleted", user_id=str(user_id))
        return True
    
    async def authenticate(self, email: str, password: str) -> Optional[User]:
        """Authenticate user with email and password."""
        user = await self.get_user_by_email(email)
        if not user:
            return None
        
        if not verify_password(password, user.hashed_password):
            return None
        
        if not user.is_active:
            return None
        
        user.last_login = datetime.now(timezone.utc)
        await self.db.commit()
        
        return user
    
    async def create_tokens(
        self,
        user: User,
        user_agent: Optional[str] = None,
        ip_address: Optional[str] = None,
    ) -> dict:
        """Create access and refresh tokens for user."""
        access_token = create_access_token(subject=user.id)
        refresh_token_obj = await create_refresh_token_db(
            self.db,
            user,
            user_agent=user_agent,
            ip_address=ip_address,
        )
        refresh_token = create_refresh_token(subject=user.id)
        
        return {
            "access_token": access_token,
            "refresh_token": refresh_token,
            "refresh_token_id": str(refresh_token_obj.id),
        }
    
    async def refresh_tokens(
        self,
        refresh_token: str,
        user_agent: Optional[str] = None,
        ip_address: Optional[str] = None,
    ) -> Optional[dict]:
        """Refresh access token using refresh token."""
        # Verify refresh token in database
        token_obj = await verify_refresh_token(self.db, refresh_token)
        if not token_obj:
            return None
        
        user = await self.get_user_by_id(token_obj.user_id)
        if not user or not user.is_active:
            return None
        
        # Revoke old refresh token
        await revoke_refresh_token(self.db, refresh_token)
        
        # Create new tokens
        return await self.create_tokens(user, user_agent, ip_address)
    
    async def logout(self, refresh_token: str) -> bool:
        """Logout user by revoking refresh token."""
        return await revoke_refresh_token(self.db, refresh_token)
    
    async def logout_all(self, user_id: UUID) -> int:
        """Logout user from all devices."""
        return await revoke_all_user_refresh_tokens(self.db, user_id)


class ItemService:
    """Service for item-related operations."""
    
    def __init__(self, db: AsyncSession):
        self.db = db
    
    async def create_item(
        self,
        item_data: ItemCreate,
        owner_id: UUID,
    ) -> Item:
        """Create a new item."""
        item = Item(
            title=item_data.title,
            description=item_data.description,
            owner_id=owner_id,
            is_public=item_data.is_public,
        )
        
        self.db.add(item)
        await self.db.commit()
        await self.db.refresh(item)
        
        logger.info("Item created", item_id=str(item.id), owner_id=str(owner_id))
        return item
    
    async def get_item(self, item_id: UUID) -> Optional[Item]:
        """Get item by ID."""
        result = await self.db.execute(select(Item).where(Item.id == item_id))
        return result.scalar_one_or_none()
    
    async def get_items(
        self,
        owner_id: Optional[UUID] = None,
        page: int = 1,
        size: int = 20,
    ) -> tuple[List[Item], int]:
        """Get paginated list of items."""
        offset = (page - 1) * size
        
        query = select(Item)
        if owner_id:
            query = query.where(Item.owner_id == owner_id)
        
        # Get total count
        count_query = query.with_only_columns(func.count(Item.id))
        count_result = await self.db.execute(count_query)
        total = count_result.scalar()
        
        # Get items
        result = await self.db.execute(
            query.order_by(Item.created_at.desc())
            .offset(offset)
            .limit(size)
        )
        items = result.scalars().all()
        
        return list(items), total
    
    async def update_item(
        self,
        item_id: UUID,
        item_data: ItemUpdate,
    ) -> Optional[Item]:
        """Update item."""
        item = await self.get_item(item_id)
        if not item:
            return None
        
        if item_data.title is not None:
            item.title = item_data.title
        
        if item_data.description is not None:
            item.description = item_data.description
        
        if item_data.is_public is not None:
            item.is_public = item_data.is_public
        
        item.updated_at = datetime.now(timezone.utc)
        
        await self.db.commit()
        await self.db.refresh(item)
        
        logger.info("Item updated", item_id=str(item_id))
        return item
    
    async def delete_item(self, item_id: UUID) -> bool:
        """Delete item."""
        item = await self.get_item(item_id)
        if not item:
            return False
        
        await self.db.delete(item)
        await self.db.commit()
        
        logger.info("Item deleted", item_id=str(item_id))
        return True