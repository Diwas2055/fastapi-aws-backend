"""Database configuration and session management."""

from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.orm import DeclarativeBase
from sqlalchemy.pool import NullPool

from app.core.config import settings


class Base(DeclarativeBase):
    """Base class for all database models."""


# Create async engine
pool_args = {
    "pool_pre_ping": settings.RDS_POOL_PRE_PING if settings.is_rds else True,
    "pool_recycle": settings.RDS_POOL_RECYCLE if settings.is_rds else -1,
}

if settings.is_rds:
    pool_args.update(
        {
            "pool_size": settings.RDS_POOL_SIZE,
            "max_overflow": settings.RDS_MAX_OVERFLOW,
            "pool_timeout": settings.RDS_POOL_TIMEOUT,
        }
    )
else:
    pool_args.update(
        {
            "pool_size": settings.DATABASE_POOL_SIZE,
            "max_overflow": settings.DATABASE_MAX_OVERFLOW,
            "pool_timeout": settings.DATABASE_POOL_TIMEOUT,
        }
    )

engine: AsyncEngine = create_async_engine(
    str(settings.DATABASE_URL),
    echo=settings.DEBUG,
    **pool_args,
    poolclass=NullPool if settings.ENVIRONMENT == "testing" else None,
)

# Create async session factory
async_session_maker = async_sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autoflush=False,
    autocommit=False,
)


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """Dependency for getting database session."""
    async with async_session_maker() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()


@asynccontextmanager
async def get_db_context() -> AsyncGenerator[AsyncSession, None]:
    """Context manager for database session outside of request cycle."""
    async with async_session_maker() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()


async def init_db() -> None:
    """Initialize database tables."""
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)


async def close_db() -> None:
    """Close database connections."""
    await engine.dispose()
