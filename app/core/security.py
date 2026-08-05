"""Security utilities for authentication and authorization."""

import secrets
from datetime import UTC, datetime, timedelta
from uuid import UUID

from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from jose import JWTError, jwt
from passlib.context import CryptContext
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.db.session import get_db
from app.models import RefreshToken, User
from app.schemas import TokenData

# Password hashing
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

# OAuth2 scheme
oauth2_scheme = OAuth2PasswordBearer(
    tokenUrl=f"{settings.API_V1_PREFIX}/auth/login",
    auto_error=False,
)


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Verify a plain password against its hash."""
    return pwd_context.verify(plain_password, hashed_password)


def get_password_hash(password: str) -> str:
    """Hash a password."""
    return pwd_context.hash(password)


def create_access_token(
    subject: str | UUID,
    expires_delta: timedelta | None = None,
    additional_claims: dict | None = None,
) -> str:
    """Create a JWT access token."""
    if expires_delta:
        expire = datetime.now(UTC) + expires_delta
    else:
        expire = datetime.now(UTC) + timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)

    to_encode = {
        "exp": expire,
        "sub": str(subject),
        "type": "access",
        "iat": datetime.now(UTC),
    }

    if additional_claims:
        to_encode.update(additional_claims)

    return jwt.encode(to_encode, settings.SECRET_KEY, algorithm=settings.ALGORITHM)


def create_refresh_token(
    subject: str | UUID,
    expires_delta: timedelta | None = None,
) -> str:
    """Create a JWT refresh token."""
    if expires_delta:
        expire = datetime.now(UTC) + expires_delta
    else:
        expire = datetime.now(UTC) + timedelta(days=settings.REFRESH_TOKEN_EXPIRE_DAYS)

    to_encode = {
        "exp": expire,
        "sub": str(subject),
        "type": "refresh",
        "iat": datetime.now(UTC),
    }

    return jwt.encode(to_encode, settings.SECRET_KEY, algorithm=settings.ALGORITHM)


def decode_token(token: str) -> TokenData:
    """Decode and validate a JWT token."""
    try:
        payload = jwt.decode(
            token,
            settings.SECRET_KEY,
            algorithms=[settings.ALGORITHM],
        )
        return TokenData(**payload)
    except JWTError as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Could not validate credentials",
            headers={"WWW-Authenticate": "Bearer"},
        ) from e


async def get_current_user(
    token: str = Depends(oauth2_scheme),
    db: AsyncSession = Depends(get_db),
) -> User:
    """Get the current authenticated user."""
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )

    if not token:
        raise credentials_exception

    token_data = decode_token(token)

    if token_data.type != "access":
        raise credentials_exception

    if token_data.sub is None:
        raise credentials_exception

    try:
        user_id = UUID(token_data.sub)
    except ValueError:
        raise credentials_exception

    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()

    if user is None:
        raise credentials_exception

    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Inactive user",
        )

    return user


async def get_current_active_superuser(
    current_user: User = Depends(get_current_user),
) -> User:
    """Get the current authenticated superuser."""
    if not current_user.is_superuser:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not enough permissions",
        )
    return current_user


async def get_current_active_superuser_or_dev(
    current_user: User = Depends(get_current_user),
) -> User:
    """Allow superuser auth, or bypass for local development.

    In development mode, returns a lightweight fake user instead of requiring
    a real JWT. Production always requires real authentication.
    """
    if settings.is_development:
        return User(
            id=UUID("00000000-0000-0000-0000-000000000000"),
            email="dev@local",
            is_superuser=True,
            is_active=True,
        )
    if not current_user.is_superuser:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not enough permissions",
        )
    return current_user


async def get_current_active_superuser_or_dev(
    db: AsyncSession = Depends(get_db),
) -> User:
    """Allow superuser auth, or bypass for local development.

    In development mode, returns a lightweight fake user instead of requiring
    a real JWT. Production always requires real authentication.
    """
    if settings.is_development:
        return User(
            id=UUID("00000000-0000-0000-0000-000000000000"),
            email="dev@local",
            is_superuser=True,
            is_active=True,
        )
    raise HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )


async def create_refresh_token_db(
    db: AsyncSession,
    user: User,
    user_agent: str | None = None,
    ip_address: str | None = None,
) -> RefreshToken:
    """Create and store a refresh token in the database."""
    token = secrets.token_urlsafe(64)
    expires_at = datetime.now(UTC) + timedelta(days=settings.REFRESH_TOKEN_EXPIRE_DAYS)

    refresh_token = RefreshToken(
        token=token,
        user_id=user.id,
        expires_at=expires_at,
        user_agent=user_agent,
        ip_address=ip_address,
    )

    db.add(refresh_token)
    await db.commit()
    await db.refresh(refresh_token)

    return refresh_token


async def verify_refresh_token(
    db: AsyncSession,
    token: str,
) -> RefreshToken | None:
    """Verify a refresh token and return it if valid."""
    result = await db.execute(
        select(RefreshToken).where(
            RefreshToken.token == token,
            RefreshToken.revoked.is_(False),
            RefreshToken.expires_at > datetime.now(UTC),
        )
    )
    return result.scalar_one_or_none()


async def revoke_refresh_token(
    db: AsyncSession,
    token: str,
) -> bool:
    """Revoke a refresh token."""
    result = await db.execute(select(RefreshToken).where(RefreshToken.token == token))
    refresh_token = result.scalar_one_or_none()

    if refresh_token:
        refresh_token.revoked = True
        await db.commit()
        return True

    return False


async def revoke_all_user_refresh_tokens(
    db: AsyncSession,
    user_id: UUID,
) -> int:
    """Revoke all refresh tokens for a user."""
    result = await db.execute(
        select(RefreshToken).where(
            RefreshToken.user_id == user_id,
            RefreshToken.revoked.is_(False),
        )
    )
    tokens = result.scalars().all()

    for token in tokens:
        token.revoked = True

    await db.commit()
    return len(tokens)
