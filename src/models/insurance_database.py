"""
Insurance Demo Database Connection
Separate database connection for insurance analytics
"""
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, Session
from typing import Generator
import logging

from src.core.config import get_settings

logger = logging.getLogger(__name__)

# Insurance database engine and session factory
insurance_engine = None
InsuranceSessionLocal = None


def init_insurance_database():
    """Initialize insurance demo database connection."""
    global insurance_engine, InsuranceSessionLocal
    
    settings = get_settings()
    
    insurance_engine = create_engine(
        settings.insurance_demo_db_url,
        pool_pre_ping=True,
        pool_recycle=300,
        echo=settings.debug
    )
    
    InsuranceSessionLocal = sessionmaker(
        autocommit=False,
        autoflush=False,
        bind=insurance_engine
    )
    
    logger.info("Insurance demo database initialized successfully")


def get_insurance_db() -> Generator[Session, None, None]:
    """
    Dependency to get insurance database session.
    
    Yields:
        Session: SQLAlchemy session for insurance_demo_db
    """
    if InsuranceSessionLocal is None:
        init_insurance_database()
    
    db = InsuranceSessionLocal()
    try:
        yield db
    finally:
        db.close()

