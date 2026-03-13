"""
Base service class providing standardized database session management.

This module provides the foundation for all service layer classes, ensuring
consistent database session handling with proper transaction management,
error handling, and resource cleanup.
"""

from contextlib import contextmanager
from typing import Generator, Optional
from sqlalchemy.orm import Session
from sqlalchemy.ext.asyncio import AsyncSession

from src.models import init_database, init_async_database
import src.models
from src.core.logging import get_logger

logger = get_logger(__name__)


class BaseService:
    """
    Base service class with standardized synchronous database session management.
    
    This class provides a consistent pattern for database operations in service layers,
    ensuring proper transaction management, error handling, and resource cleanup.
    
    Key Features:
    - Automatic commit on successful operations
    - Automatic rollback on exceptions
    - Proper session cleanup
    - Lazy database initialization
    - Comprehensive error logging
    """
    
    @contextmanager
    def get_db_session(self) -> Generator[Session, None, None]:
        """
        Context manager for database sessions with automatic transaction management.
        
        This method provides a database session with the following guarantees:
        - Automatic commit on successful completion
        - Automatic rollback on any exception
        - Proper session cleanup in all cases
        - Database initialization if needed
        
        Usage:
            with self.get_db_session() as db:
                user = db.query(User).filter(User.id == user_id).first()
                # Automatic commit happens here on success
        
        Yields:
            Session: SQLAlchemy synchronous database session
            
        Raises:
            Exception: Re-raises any exception after proper rollback
        """
        # Ensure database is initialized
        if src.models.SessionLocal is None:
            logger.info("Initializing database for service layer session")
            init_database()

        # Double-check after initialization
        if src.models.SessionLocal is None:
            logger.error("SessionLocal is still None after init_database() call")
            raise RuntimeError("Failed to initialize database session factory")

        session = src.models.SessionLocal()
        try:
            logger.debug("Database session created for service operation")
            yield session
            session.commit()
            logger.debug("Database session committed successfully")
        except Exception as e:
            logger.error(f"Database session error, rolling back: {str(e)}")
            session.rollback()
            raise
        finally:
            session.close()
            logger.debug("Database session closed")


class AsyncBaseService:
    """
    Base service class with standardized asynchronous database session management.
    
    This class provides a consistent pattern for async database operations in service layers,
    ensuring proper transaction management, error handling, and resource cleanup.
    
    Key Features:
    - Automatic commit on successful operations
    - Automatic rollback on exceptions
    - Proper session cleanup
    - Lazy async database initialization
    - Comprehensive error logging
    """
    
    async def get_async_session_factory(self):
        """
        Get the AsyncSessionLocal factory, initializing if needed.
        
        Returns:
            AsyncSessionLocal: The async session factory
        """
        if src.models.AsyncSessionLocal is None:
            logger.info("Initializing async database for service layer session")
            init_async_database()
        return src.models.AsyncSessionLocal
    
    async def execute_with_session(self, operation):
        """
        Execute an async operation with proper session management.
        
        This method provides an async database session with the following guarantees:
        - Automatic commit on successful completion
        - Automatic rollback on any exception
        - Proper session cleanup in all cases
        - Database initialization if needed
        
        Args:
            operation: Async callable that takes a session parameter
            
        Usage:
            async def my_operation(session):
                result = await session.execute(select(User))
                return result.scalars().all()
            
            users = await self.execute_with_session(my_operation)
        
        Returns:
            Any: Result of the operation
            
        Raises:
            Exception: Re-raises any exception after proper rollback
        """
        AsyncSession = await self.get_async_session_factory()
        
        async with AsyncSession() as session:
            try:
                logger.debug("Async database session created for service operation")
                result = await operation(session)
                await session.commit()
                logger.debug("Async database session committed successfully")
                return result
            except Exception as e:
                logger.error(f"Async database session error, rolling back: {str(e)}")
                await session.rollback()
                raise
            finally:
                await session.close()
                logger.debug("Async database session closed")


class DatabaseServiceMixin:
    """
    Mixin class providing database session utilities for services that need both sync and async.
    
    This mixin can be used alongside other base classes to provide database session
    management capabilities without requiring inheritance from BaseService.
    """
    
    @contextmanager
    def get_db_session(self) -> Generator[Session, None, None]:
        """
        Context manager for database sessions with automatic transaction management.
        
        Identical to BaseService.get_db_session() but available as a mixin.
        """
        if src.models.SessionLocal is None:
            logger.info("Initializing database for mixin session")
            init_database()
        
        # Double-check after initialization
        if src.models.SessionLocal is None:
            logger.error("SessionLocal is still None after init_database() call")
            raise RuntimeError("Failed to initialize database session factory")
        
        session = src.models.SessionLocal()
        try:
            logger.debug("Mixin database session created")
            yield session
            session.commit()
            logger.debug("Mixin database session committed successfully")
        except Exception as e:
            logger.error(f"Mixin database session error, rolling back: {str(e)}")
            session.rollback()
            raise
        finally:
            session.close()
            logger.debug("Mixin database session closed")
    
    async def execute_async_with_session(self, operation):
        """
        Execute an async operation with proper session management.
        
        Identical to AsyncBaseService.execute_with_session() but available as a mixin.
        """
        if src.models.AsyncSessionLocal is None:
            logger.info("Initializing async database for mixin session")
            init_async_database()

        async with src.models.AsyncSessionLocal() as session:
            try:
                logger.debug("Mixin async database session created")
                result = await operation(session)
                await session.commit()
                logger.debug("Mixin async database session committed successfully")
                return result
            except Exception as e:
                logger.error(f"Mixin async database session error, rolling back: {str(e)}")
                await session.rollback()
                raise
            finally:
                await session.close()
                logger.debug("Mixin async database session closed")


# Utility functions for backward compatibility and migration
@contextmanager
def get_service_db_session() -> Generator[Session, None, None]:
    """
    Standalone function for database session management.

    This function provides the same session management as BaseService.get_db_session()
    but can be used in services that haven't been refactored to inherit from BaseService yet.

    Usage:
        with get_service_db_session() as db:
            user = db.query(User).filter(User.id == user_id).first()

    Yields:
        Session: SQLAlchemy synchronous database session
    """
    if src.models.SessionLocal is None:
        logger.info("Initializing database for standalone session")
        init_database()

    # Double-check after initialization
    if src.models.SessionLocal is None:
        logger.error("SessionLocal is still None after init_database() call")
        raise RuntimeError("Failed to initialize database session factory")

    session = src.models.SessionLocal()
    try:
        logger.debug("Standalone database session created")
        yield session
        session.commit()
        logger.debug("Standalone database session committed successfully")
    except Exception as e:
        logger.error(f"Standalone database session error, rolling back: {str(e)}")
        session.rollback()
        raise
    finally:
        session.close()
        logger.debug("Standalone database session closed")
