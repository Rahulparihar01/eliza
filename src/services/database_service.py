"""
AI Enablement Platform - Database Service

Service for managing database connections, health checks, and operations.
"""

import logging
from typing import Dict, Any, Optional
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from src.models import (
    init_database,
    check_database_health,
    Base,
    User,
    Customer,
    CustomerAIProvider
)
from src.services.base_service import BaseService
from core.config import get_settings

logger = logging.getLogger(__name__)


class DatabaseService(BaseService):
    """Service for database operations and management."""
    
    def __init__(self):
        self.settings = get_settings()
        self._initialized = False
    
    async def initialize(self) -> bool:
        """
        Initialize database connection and create tables if needed.
        
        Returns:
            bool: True if initialization successful
        """
        try:
            # Initialize database connection
            init_database()
            self._initialized = True
            
            logger.info("Database service initialized successfully")
            return True
            
        except Exception as e:
            logger.error(f"Failed to initialize database service: {e}")
            return False
    
    async def get_health_status(self) -> Dict[str, Any]:
        """
        Get comprehensive database health status.
        
        Returns:
            dict: Database health information
        """
        if not self._initialized:
            return {
                "status": "unhealthy",
                "message": "Database service not initialized",
                "details": {}
            }
        
        # Get basic health check
        health_status = await check_database_health()
        
        # Add additional checks
        try:
            # Test basic operations
            with self.get_db_session() as db:
                # Test table existence
                tables_exist = self._check_tables_exist(db)
                health_status["details"]["tables_exist"] = tables_exist
                
                # Test basic query
                customer_count = db.query(Customer).count()
                user_count = db.query(User).count()
                
                health_status["details"]["customer_count"] = customer_count
                health_status["details"]["user_count"] = user_count
                
        except Exception as e:
            logger.warning(f"Extended database health check failed: {e}")
            health_status["details"]["extended_check_error"] = str(e)
        
        return health_status
    
    def _check_tables_exist(self, db: Session) -> Dict[str, bool]:
        """Check if required tables exist."""
        tables = {}
        
        try:
            # Check each table
            tables["customers"] = db.execute("SELECT 1 FROM customers LIMIT 1").fetchone() is not None or True
        except:
            tables["customers"] = False
        
        try:
            tables["users"] = db.execute("SELECT 1 FROM users LIMIT 1").fetchone() is not None or True
        except:
            tables["users"] = False
        
        try:
            tables["customer_ai_providers"] = db.execute("SELECT 1 FROM customer_ai_providers LIMIT 1").fetchone() is not None or True
        except:
            tables["customer_ai_providers"] = False
        
        try:
            tables["user_sessions"] = db.execute("SELECT 1 FROM user_sessions LIMIT 1").fetchone() is not None or True
        except:
            tables["user_sessions"] = False
        
        return tables
    
    async def create_default_customer(self, customer_id: str = "local-dev") -> Optional[Customer]:
        """
        Create a default customer for development/testing.
        
        Args:
            customer_id: Customer ID to create
            
        Returns:
            Customer: Created customer or None if failed
        """
        try:
            with self.get_db_session() as db:
                # Check if customer already exists
                existing = db.query(Customer).filter(Customer.customer_id == customer_id).first()
                if existing:
                    logger.info(f"Customer {customer_id} already exists")
                    return existing
                
                # Create new customer
                customer = Customer(
                    customer_id=customer_id,
                    name="Local Development Customer",
                    display_name="Local Development",
                    contact_email="dev@localhost",
                    is_active=True,
                    subscription_tier="development",
                    max_users=100,
                    max_documents=10000,
                    max_api_calls_per_month=100000
                )
                
                db.add(customer)
                db.flush()  # Flush to get the ID without committing yet
                customer_id_value = customer.id
                # Auto-commit handled by BaseService context manager

                logger.info(f"Created default customer: {customer_id} (ID: {customer_id_value})")
                return customer
                
        except Exception as e:
            logger.error(f"Failed to create default customer: {e}")
            return None
    
    async def setup_development_data(self) -> bool:
        """
        Set up default data for development environment.
        
        Returns:
            bool: True if setup successful
        """
        try:
            # Create default customer (use configured customer_id)
            # Admin user creation is handled by scripts/init_tenant.py
            customer = await self.create_default_customer(self.settings.customer_id)
            if not customer:
                return False
            
            logger.info(f"Development data setup completed successfully for customer: {self.settings.customer_id}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to setup development data: {e}")
            return False
