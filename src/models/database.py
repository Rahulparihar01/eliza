"""
AI Enablement Platform - Database Models Base

Base database configuration and shared models.
Supports both synchronous and asynchronous database operations.
"""

from sqlalchemy import create_engine, MetaData
from sqlalchemy.orm import declarative_base, sessionmaker, Session
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
from sqlalchemy import Column, Integer, String, DateTime, Boolean, Text, JSON
from sqlalchemy.sql import func
import sqlalchemy as sa
from typing import Generator, AsyncGenerator
import logging

from src.core.config import get_settings

logger = logging.getLogger(__name__)

# Database metadata and base class
metadata = MetaData()
Base = declarative_base(metadata=metadata)

# Database engines and sessions
engine = None
SessionLocal = None
async_engine = None
AsyncSessionLocal = None


def init_database():
    """Initialize synchronous database connection and session factory."""
    global engine, SessionLocal
    
    settings = get_settings()
    
    # Create synchronous engine
    engine = create_engine(
        settings.database_url,
        pool_pre_ping=True,
        pool_recycle=300,
        echo=settings.debug  # Log SQL queries in debug mode
    )
    
    # Create synchronous session factory
    SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    
    logger.info("Synchronous database initialized successfully")


def init_async_database():
    """Initialize asynchronous database connection and session factory."""
    global async_engine, AsyncSessionLocal
    
    settings = get_settings()
    
    # Convert sync database URL to async (postgresql:// -> postgresql+asyncpg://)
    async_database_url = settings.database_url.replace(
        "postgresql://", "postgresql+asyncpg://"
    )
    
    # Create async engine
    async_engine = create_async_engine(
        async_database_url,
        pool_pre_ping=True,
        pool_recycle=300,
        echo=settings.debug  # Log SQL queries in debug mode
    )
    
    # Create async session factory
    AsyncSessionLocal = async_sessionmaker(
        async_engine,
        class_=AsyncSession,
        expire_on_commit=False
    )
    
    logger.info("Asynchronous database initialized successfully")


def get_db() -> Generator[Session, None, None]:
    """
    Dependency to get synchronous database session.
    
    Yields:
        Session: SQLAlchemy synchronous database session
    """
    if SessionLocal is None:
        init_database()
    
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


async def get_async_session() -> AsyncGenerator[AsyncSession, None]:
    """
    Dependency to get asynchronous database session.
    
    Yields:
        AsyncSession: SQLAlchemy asynchronous database session
    """
    if AsyncSessionLocal is None:
        init_async_database()
    
    async with AsyncSessionLocal() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()


async def check_database_health() -> dict:
    """
    Check database connectivity and health (async version).
    
    Returns:
        dict: Database health status
    """
    try:
        if async_engine is None:
            init_async_database()
        
        # Test async connection
        async with async_engine.begin() as conn:
            result = await conn.execute(sa.text("SELECT 1"))
            await result.fetchone()
        
        return {
            "status": "healthy",
            "message": "Database connection successful",
            "details": {
                "engine_pool_size": async_engine.pool.size(),
                "engine_pool_checked_in": async_engine.pool.checkedin(),
                "engine_pool_checked_out": async_engine.pool.checkedout()
            }
        }
    
    except Exception as e:
        logger.error(f"Database health check failed: {e}")
        return {
            "status": "unhealthy",
            "message": f"Database connection failed: {str(e)}",
            "details": {}
        }


def check_database_health_sync() -> dict:
    """
    Check database connectivity and health (synchronous version).
    
    Returns:
        dict: Database health status
    """
    try:
        if engine is None:
            init_database()
        
        # Test synchronous connection
        with engine.connect() as conn:
            result = conn.execute(sa.text("SELECT 1"))
            result.fetchone()
        
        return {
            "status": "healthy",
            "message": "Database connection successful",
            "details": {
                "engine_pool_size": engine.pool.size(),
                "engine_pool_checked_in": engine.pool.checkedin(),
                "engine_pool_checked_out": engine.pool.checkedout()
            }
        }
    
    except Exception as e:
        logger.error(f"Database health check failed: {e}")
        return {
            "status": "unhealthy",
            "message": f"Database connection failed: {str(e)}",
            "details": {}
        }


class BaseModel(Base):
    """Base model class with common fields."""
    
    __abstract__ = True
    
    id = Column(Integer, primary_key=True, index=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)
    
    def to_dict(self) -> dict:
        """Convert model instance to dictionary."""
        return {
            column.name: getattr(self, column.name)
            for column in self.__table__.columns
        }
    
    def __repr__(self):
        return f"<{self.__class__.__name__}(id={self.id})>"
