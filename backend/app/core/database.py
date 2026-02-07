"""
Database Configuration
SQLAlchemy async engine and session management
"""

from contextlib import asynccontextmanager
from typing import AsyncGenerator, Optional

from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
    AsyncEngine,
)
from sqlalchemy.orm import declarative_base
from sqlalchemy.pool import NullPool

from app.core.config import settings


# Base class for models
Base = declarative_base()

# Global engine and session factory (lazy initialization)
_engine: Optional[AsyncEngine] = None
_async_session_factory: Optional[async_sessionmaker] = None


def get_async_database_url(url: str) -> str:
    """Convert database URL to async version"""
    if url.startswith("postgresql://"):
        return url.replace("postgresql://", "postgresql+asyncpg://", 1)
    elif url.startswith("postgres://"):
        return url.replace("postgres://", "postgresql+asyncpg://", 1)
    return url


def get_engine() -> AsyncEngine:
    """Get or create the async engine (lazy initialization)"""
    global _engine
    if _engine is None:
        async_database_url = get_async_database_url(settings.database_url)
        # Remove any query params from URL (we'll handle them in connect_args)
        if "?" in async_database_url:
            async_database_url = async_database_url.split("?")[0]
        
        _engine = create_async_engine(
            async_database_url,
            echo=settings.debug,
            # Use NullPool to avoid connection issues on Windows
            poolclass=NullPool,
            # Explicitly disable SSL for local development
            connect_args={"ssl": False},
        )
    return _engine


def get_session_factory() -> async_sessionmaker:
    """Get or create the session factory"""
    global _async_session_factory
    if _async_session_factory is None:
        _async_session_factory = async_sessionmaker(
            get_engine(),
            class_=AsyncSession,
            expire_on_commit=False,
            autoflush=False,
        )
    return _async_session_factory


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """
    Dependency for getting database sessions.
    Yields a session and ensures it's closed after use.
    """
    session_factory = get_session_factory()
    async with session_factory() as session:
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
    """
    Context manager for database sessions.
    Useful for background tasks and scripts.
    """
    session_factory = get_session_factory()
    async with session_factory() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()


async def init_db() -> None:
    """Initialize database tables"""
    engine = get_engine()
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)


async def close_db() -> None:
    """Close database connections"""
    global _engine
    if _engine is not None:
        await _engine.dispose()
        _engine = None
