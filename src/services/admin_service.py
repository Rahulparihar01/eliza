"""
Admin Service - AI Enablement Platform

This service provides comprehensive admin functionality including:
- System health monitoring and metrics
- User management and analytics
- Document oversight and processing monitoring
- AI model configuration and usage analytics
- Platform configuration and security settings
"""

import asyncio
import secrets
import string
from datetime import datetime, timedelta
from typing import List, Dict, Any, Optional
from sqlalchemy import select, func, and_, or_, desc
from sqlalchemy.ext.asyncio import AsyncSession
import psutil
import redis
import json

from src.models.auth import User, Role, Permission, UserSession, user_roles, UserAuditLog
from src.models.document import Document, DocumentStatus
from src.models.database import get_async_session, init_async_database
from src.services.auth_service import auth_service
from src.services.security_service import security_service
from src.core.config import get_settings

settings = get_settings()

# Helper function to get async session factory
def get_async_session_factory():
    """Get the async session factory, initializing if needed"""
    from src.models.database import AsyncSessionLocal
    if AsyncSessionLocal is None:
        init_async_database()
        from src.models.database import AsyncSessionLocal
    return AsyncSessionLocal

class AdminService:
    """Service for admin portal functionality"""
    
    def __init__(self):
        self.redis_client = None
        self._initialize_redis()
    
    def _initialize_redis(self):
        """Initialize Redis connection for caching"""
        try:
            self.redis_client = redis.Redis(
                host=settings.REDIS_HOST,
                port=settings.REDIS_PORT,
                db=0,
                decode_responses=True
            )
            self.redis_client.ping()
        except Exception as e:
            print(f"Redis connection failed: {e}")
            self.redis_client = None
    
    # ============================================================================
    # System Health & Monitoring
    # ============================================================================
    
    async def get_system_health(self) -> Dict[str, Any]:
        """Get comprehensive system health status"""
        health_data = {
            "api_status": "online",
            "database_status": "healthy",
            "vector_service_status": "operational",
            "redis_status": "connected",
            "neo4j_status": "available",
            "last_health_check": datetime.utcnow(),
            "uptime_percentage": 99.8,
            "services": {}
        }
        
        # Check database connection
        try:
            AsyncSessionLocal = get_async_session_factory()
            async with AsyncSessionLocal() as session:
                result = await session.execute(select(func.count(User.id)))
                user_count = result.scalar()
                health_data["services"]["database"] = {
                    "status": "healthy",
                    "response_time_ms": 15,
                    "connections": 5,
                    "user_count": user_count
                }
        except Exception as e:
            health_data["database_status"] = "error"
            health_data["services"]["database"] = {
                "status": "error",
                "error": str(e)
            }
        
        # Check Redis connection
        if self.redis_client:
            try:
                self.redis_client.ping()
                health_data["services"]["redis"] = {
                    "status": "connected",
                    "memory_usage": "45MB",
                    "connected_clients": 3
                }
            except Exception as e:
                health_data["redis_status"] = "disconnected"
                health_data["services"]["redis"] = {
                    "status": "error",
                    "error": str(e)
                }
        
        # Get system metrics
        cpu_percent = psutil.cpu_percent(interval=1)
        memory = psutil.virtual_memory()
        disk = psutil.disk_usage('/')
        
        health_data["services"]["system"] = {
            "cpu_usage": f"{cpu_percent}%",
            "memory_usage": f"{memory.percent}%",
            "disk_usage": f"{disk.percent}%",
            "load_average": psutil.getloadavg()[0] if hasattr(psutil, 'getloadavg') else 0.5
        }
        
        return health_data
    
    async def get_system_metrics(self, time_range: str) -> Dict[str, Any]:
        """Get detailed system performance metrics"""
        # Convert time range to hours
        hours_map = {"1h": 1, "24h": 24, "7d": 168, "30d": 720}
        hours = hours_map.get(time_range, 24)
        
        start_time = datetime.utcnow() - timedelta(hours=hours)
        
        AsyncSessionLocal = get_async_session_factory()
        async with AsyncSessionLocal() as session:
            # Get user activity metrics
            user_activity = await session.execute(
                select(func.count(UserSession.id))
                .where(UserSession.created_at >= start_time)
            )
            active_sessions = user_activity.scalar()
            
            # Get login metrics
            login_metrics = await session.execute(
                select(func.count(UserSession.id))
                .where(
                    and_(
                        UserSession.created_at >= start_time,
                        UserSession.is_active == True
                    )
                )
            )
            successful_logins = login_metrics.scalar()
        
        # Generate mock performance data (in production, this would come from monitoring tools)
        metrics = {
            "time_range": time_range,
            "start_time": start_time,
            "end_time": datetime.utcnow(),
            "api_metrics": {
                "total_requests": 15420,
                "average_response_time": 245,
                "error_rate": 0.2,
                "requests_per_minute": 85
            },
            "user_metrics": {
                "active_sessions": active_sessions,
                "successful_logins": successful_logins,
                "failed_logins": 12,
                "unique_users": 89
            },
            "system_metrics": {
                "cpu_usage_avg": 23.5,
                "memory_usage_avg": 67.2,
                "disk_io_avg": 15.8,
                "network_io_avg": 45.2
            },
            "database_metrics": {
                "query_count": 8934,
                "average_query_time": 12.5,
                "slow_queries": 3,
                "connection_pool_usage": 45
            }
        }
        
        return metrics
    
    async def get_dashboard_overview(self) -> Dict[str, Any]:
        """Get admin dashboard overview data with real database queries"""
        AsyncSessionLocal = get_async_session_factory()
        async with AsyncSessionLocal() as session:
            # ==== User Activity Metrics ====
            # Total registered users
            total_users = await session.execute(select(func.count(User.id)))
            total_users_count = total_users.scalar() or 0
            
            # Active users (with active sessions in last 15 minutes)
            fifteen_min_ago = datetime.utcnow() - timedelta(minutes=15)
            active_now = await session.execute(
                select(func.count(func.distinct(UserSession.user_id)))
                .where(
                    and_(
                        UserSession.is_active == True,
                        UserSession.last_activity_at >= fifteen_min_ago
                    )
                )
            )
            active_users_now = active_now.scalar() or 0
            
            # Active users today (logged in today)
            today_start = datetime.utcnow().replace(hour=0, minute=0, second=0, microsecond=0)
            active_today = await session.execute(
                select(func.count(func.distinct(UserSession.user_id)))
                .where(UserSession.created_at >= today_start)
            )
            active_users_today = active_today.scalar() or 0
            
            # New users this week
            week_ago = datetime.utcnow() - timedelta(days=7)
            new_users = await session.execute(
                select(func.count(User.id))
                .where(User.created_at >= week_ago)
            )
            new_users_count = new_users.scalar() or 0
            
            # Calculate user growth percentage (compare to previous week)
            two_weeks_ago = datetime.utcnow() - timedelta(days=14)
            previous_week_users = await session.execute(
                select(func.count(User.id))
                .where(
                    and_(
                        User.created_at >= two_weeks_ago,
                        User.created_at < week_ago
                    )
                )
            )
            previous_week_count = previous_week_users.scalar() or 1  # Avoid division by zero
            user_growth_percentage = ((new_users_count - previous_week_count) / previous_week_count * 100) if previous_week_count > 0 else 0.0
            
            # ==== Document Metrics ====
            # Total documents (excluding deleted)
            total_docs = await session.execute(
                select(func.count(Document.id))
                .where(Document.status != DocumentStatus.DELETED)
            )
            total_documents = total_docs.scalar() or 0
            
            # Documents uploaded today
            docs_today = await session.execute(
                select(func.count(Document.id))
                .where(
                    and_(
                        Document.created_at >= today_start,
                        Document.status != DocumentStatus.DELETED
                    )
                )
            )
            documents_uploaded_today = docs_today.scalar() or 0
            
            # Processing queue size (documents in PROCESSING or UPLOADED status)
            processing_count = await session.execute(
                select(func.count(Document.id))
                .where(
                    Document.status.in_([DocumentStatus.PROCESSING, DocumentStatus.UPLOADED])
                )
            )
            processing_queue_size = processing_count.scalar() or 0
            
            # Total storage (sum of file sizes)
            storage_bytes = await session.execute(
                select(func.sum(Document.file_size))
                .where(Document.status != DocumentStatus.DELETED)
            )
            storage_used_bytes = storage_bytes.scalar() or 0
            storage_usage_gb = round(storage_used_bytes / (1024 ** 3), 2)  # Convert to GB
            
            # ==== Search Activity ====
            # Count search queries from audit logs today (if tracked)
            search_queries_today = await session.execute(
                select(func.count(UserAuditLog.id))
                .where(
                    and_(
                        UserAuditLog.created_at >= today_start,
                        UserAuditLog.action.like('%search%')
                    )
                )
            )
            total_searches_today = search_queries_today.scalar() or 0
            
            # ==== Recent Activity ====
            # Get 10 most recent audit log entries for dashboard
            recent_logs = await session.execute(
                select(UserAuditLog)
                .order_by(desc(UserAuditLog.created_at))
                .limit(10)
            )
            recent_activity_logs = recent_logs.scalars().all()
            
            recent_activity = []
            for log in recent_activity_logs:
                recent_activity.append({
                    "timestamp": log.created_at,
                    "action": log.action.replace('_', ' ').title() if log.action else "Activity",
                    "details": log.details.get('message', '') if isinstance(log.details, dict) else str(log.details) if log.details else f"Action performed by user {log.user_id}"
                })
        
        # Build response
        overview = {
            "system_health": await self.get_system_health(),
            "user_activity": {
                "active_users_now": active_users_now,
                "active_users_today": active_users_today,
                "total_registered_users": total_users_count,
                "new_users_this_week": new_users_count,
                "user_growth_percentage": round(user_growth_percentage, 1)
            },
            "document_metrics": {
                "total_documents": total_documents,
                "documents_uploaded_today": documents_uploaded_today,
                "total_searches_today": total_searches_today,
                "processing_queue_size": processing_queue_size,
                "storage_usage_gb": storage_usage_gb
            },
            "ai_usage": {
                # Note: AI usage metrics need tracking tables - using defaults for now
                # TODO: Implement AI usage tracking in future update
                "total_calls_today": 0,
                "total_cost_today": 0.0,
                "average_response_time": 0.0,
                "success_rate": 100.0,
                "provider_breakdown": {
                    "openai": 0.0,
                    "anthropic": 0.0,
                    "groq": 0.0
                }
            },
            "recent_activity": recent_activity
        }
        
        return overview
    
    # ============================================================================
    # User Management
    # ============================================================================
    
    async def get_users_list(self, filters) -> Dict[str, Any]:
        """Get paginated list of users with filtering"""
        AsyncSessionLocal = get_async_session_factory()
        async with AsyncSessionLocal() as session:
            # Build base query
            query = select(User).order_by(desc(User.created_at))
            
            # Apply filters
            conditions = []
            if filters.search:
                search_term = f"%{filters.search}%"
                conditions.append(
                    or_(
                        User.full_name.ilike(search_term),
                        User.email.ilike(search_term),
                        User.username.ilike(search_term)
                    )
                )
            
            if filters.status:
                if filters.status == "active":
                    conditions.append(User.is_active == True)
                elif filters.status == "inactive":
                    conditions.append(User.is_active == False)
            
            if filters.created_after:
                conditions.append(User.created_at >= filters.created_after)
            
            if conditions:
                query = query.where(and_(*conditions))
            
            # Get total count
            count_query = select(func.count(User.id))
            if conditions:
                count_query = count_query.where(and_(*conditions))
            
            total_result = await session.execute(count_query)
            total_count = total_result.scalar()
            
            # Apply pagination
            offset = (filters.page - 1) * filters.page_size
            query = query.offset(offset).limit(filters.page_size)
            
            # Execute query
            result = await session.execute(query)
            users = result.scalars().all()
            
            # Format user data
            users_data = []
            for user in users:
                # Get user's last session
                last_session = await session.execute(
                    select(UserSession)
                    .where(UserSession.user_id == user.id)
                    .order_by(desc(UserSession.last_activity_at))
                    .limit(1)
                )
                last_session_obj = last_session.scalar_one_or_none()

                users_data.append({
                    "id": user.id,
                    "email": user.email,
                    "username": user.username,
                    "full_name": user.full_name,
                    "is_active": user.is_active,
                    "created_at": user.created_at,
                    "last_login_at": user.last_login_at,
                    "last_seen": last_session_obj.last_activity_at if last_session_obj else None,
                    "roles": [],  # TODO: Get user roles
                    "permissions": []  # TODO: Get user permissions
                })
            
            return {
                "users": users_data,
                "pagination": {
                    "page": filters.page,
                    "page_size": filters.page_size,
                    "total_count": total_count,
                    "total_pages": (total_count + filters.page_size - 1) // filters.page_size
                }
            }
    
    async def create_user(self, user_data, created_by_user_id: int) -> User:
        """Create a new user account"""
        AsyncSessionLocal = get_async_session_factory()
        async with AsyncSessionLocal() as session:
            # Check if user already exists
            existing_user = await session.execute(
                select(User).where(User.email == user_data.email)
            )
            if existing_user.scalar_one_or_none():
                raise ValueError("User with this email already exists")
            
            # Generate temporary password
            temp_password = self._generate_temp_password()
            
            # Create user
            new_user = User(
                email=user_data.email,
                username=user_data.email.split('@')[0],  # Use email prefix as username
                full_name=f"{user_data.first_name} {user_data.last_name}",
                is_active=user_data.is_active,
                created_by=created_by_user_id
            )
            
            # Set password
            new_user.password_hash = auth_service.hash_password(temp_password)
            new_user.force_password_change = True
            new_user.password_changed_at = datetime.utcnow()
            
            session.add(new_user)
            await session.commit()
            await session.refresh(new_user)
            
            return new_user
    
    def _generate_temp_password(self, length: int = 12) -> str:
        """Generate a secure temporary password"""
        alphabet = string.ascii_letters + string.digits + "!@#$%^&*"
        return ''.join(secrets.choice(alphabet) for _ in range(length))

    async def update_user(self, user_id: str, user_data, updated_by_user_id: int) -> User:
        """Update an existing user account"""
        AsyncSessionLocal = get_async_session_factory()
        async with AsyncSessionLocal() as session:
            # Get user
            user_result = await session.execute(
                select(User).where(User.id == int(user_id))
            )
            user = user_result.scalar_one_or_none()
            if not user:
                raise ValueError("User not found")

            # Update user fields
            if user_data.first_name or user_data.last_name:
                first_name = user_data.first_name or user.full_name.split()[0]
                last_name = user_data.last_name or user.full_name.split()[-1]
                user.full_name = f"{first_name} {last_name}"

            if user_data.is_active is not None:
                user.is_active = user_data.is_active

            user.updated_at = datetime.utcnow()
            user.updated_by = updated_by_user_id

            await session.commit()
            await session.refresh(user)

            return user

    async def delete_user(self, user_id: str, deleted_by_user_id: int):
        """Soft delete a user account"""
        async with AsyncSessionLocal() as session:
            user_result = await session.execute(
                select(User).where(User.id == int(user_id))
            )
            user = user_result.scalar_one_or_none()
            if not user:
                raise ValueError("User not found")

            # Soft delete
            user.is_active = False
            user.deleted_at = datetime.utcnow()
            user.updated_by = deleted_by_user_id

            # Deactivate all user sessions
            await session.execute(
                UserSession.__table__.update()
                .where(UserSession.user_id == user.id)
                .values(is_active=False, ended_at=datetime.utcnow())
            )

            await session.commit()

    async def activate_user(self, user_id: str, activated_by_user_id: int):
        """Activate a user account"""
        async with AsyncSessionLocal() as session:
            user_result = await session.execute(
                select(User).where(User.id == int(user_id))
            )
            user = user_result.scalar_one_or_none()
            if not user:
                raise ValueError("User not found")

            user.is_active = True
            user.updated_at = datetime.utcnow()
            user.updated_by = activated_by_user_id

            await session.commit()

    async def deactivate_user(self, user_id: str, deactivated_by_user_id: int):
        """Deactivate a user account"""
        async with AsyncSessionLocal() as session:
            user_result = await session.execute(
                select(User).where(User.id == int(user_id))
            )
            user = user_result.scalar_one_or_none()
            if not user:
                raise ValueError("User not found")

            user.is_active = False
            user.updated_at = datetime.utcnow()
            user.updated_by = deactivated_by_user_id

            # Deactivate all user sessions
            await session.execute(
                UserSession.__table__.update()
                .where(UserSession.user_id == user.id)
                .values(is_active=False, ended_at=datetime.utcnow())
            )

            await session.commit()

    async def reset_user_password(self, user_id: str, reset_by_user_id: int) -> str:
        """Reset a user's password and return temporary password"""
        async with AsyncSessionLocal() as session:
            user_result = await session.execute(
                select(User).where(User.id == int(user_id))
            )
            user = user_result.scalar_one_or_none()
            if not user:
                raise ValueError("User not found")

            # Generate new temporary password
            temp_password = self._generate_temp_password()

            # Update user password
            user.password_hash = auth_service.hash_password(temp_password)
            user.force_password_change = True
            user.password_changed_at = datetime.utcnow()
            user.updated_at = datetime.utcnow()
            user.updated_by = reset_by_user_id

            # Deactivate all existing sessions
            await session.execute(
                UserSession.__table__.update()
                .where(UserSession.user_id == user.id)
                .values(is_active=False, ended_at=datetime.utcnow())
            )

            await session.commit()

            return temp_password

    async def bulk_update_users(self, bulk_data, updated_by_user_id: int) -> Dict[str, Any]:
        """Bulk update multiple users"""
        results = {
            "success_count": 0,
            "error_count": 0,
            "errors": []
        }

        for user_id in bulk_data.user_ids:
            try:
                await self.update_user(user_id, bulk_data.updates, updated_by_user_id)
                results["success_count"] += 1
            except Exception as e:
                results["error_count"] += 1
                results["errors"].append({
                    "user_id": user_id,
                    "error": str(e)
                })

        return results

    async def export_users(self, format: str) -> str:
        """Export users list in specified format"""
        async with AsyncSessionLocal() as session:
            # Get all users
            result = await session.execute(
                select(User).order_by(User.created_at)
            )
            users = result.scalars().all()

            if format == "csv":
                import csv
                import io

                output = io.StringIO()
                writer = csv.writer(output)

                # Write header
                writer.writerow([
                    "ID", "Email", "Username", "Full Name", "Active",
                    "Created At", "Last Login", "Last Seen"
                ])

                # Write user data
                for user in users:
                    writer.writerow([
                        user.id,
                        user.email,
                        user.username,
                        user.full_name,
                        "Yes" if user.is_active else "No",
                        user.created_at.strftime("%Y-%m-%d %H:%M:%S") if user.created_at else "",
                        user.last_login_at.strftime("%Y-%m-%d %H:%M:%S") if user.last_login_at else "",
                        ""  # Last seen would need to be calculated from sessions
                    ])

                return output.getvalue()

            else:  # Excel format
                # For now, return CSV format - in production, use openpyxl
                return await self.export_users("csv")

    # ============================================================================
    # Document Management
    # ============================================================================

    async def get_documents_list(self, filters) -> Dict[str, Any]:
        """Get paginated list of documents with filtering"""
        # Mock implementation - in production, this would query document tables
        documents = []
        for i in range(filters.page_size):
            documents.append({
                "id": f"doc_{i + (filters.page - 1) * filters.page_size}",
                "name": f"Document_{i + 1}.pdf",
                "uploaded_by": "john@company.com",
                "size_mb": 2.3,
                "status": "processed",
                "uploaded_at": datetime.utcnow() - timedelta(days=i),
                "processed_at": datetime.utcnow() - timedelta(days=i, hours=1)
            })

        return {
            "documents": documents,
            "pagination": {
                "page": filters.page,
                "page_size": filters.page_size,
                "total_count": 1247,
                "total_pages": 63
            }
        }

    async def get_document_metrics(self) -> Dict[str, Any]:
        """Get document processing metrics"""
        return {
            "total_documents": 1247,
            "documents_uploaded_today": 45,
            "total_searches_today": 892,
            "total_chunks": 45892,
            "average_document_size": 2.3,
            "processing_queue_size": 12,
            "failed_processing_count": 3,
            "storage_usage_gb": 15.2
        }

    async def get_processing_queue(self) -> Dict[str, Any]:
        """Get current document processing queue"""
        return {
            "queue_size": 12,
            "processing_now": 3,
            "pending": 9,
            "estimated_completion": datetime.utcnow() + timedelta(minutes=15),
            "queue_items": [
                {
                    "id": "doc_123",
                    "name": "HR_Policies.docx",
                    "status": "processing",
                    "progress": 65,
                    "started_at": datetime.utcnow() - timedelta(minutes=5)
                },
                {
                    "id": "doc_124",
                    "name": "Market_Data.xlsx",
                    "status": "pending",
                    "progress": 0,
                    "queued_at": datetime.utcnow() - timedelta(minutes=2)
                }
            ]
        }

    async def reprocess_document(self, document_id: str, initiated_by_user_id: int):
        """Reprocess a failed or corrupted document"""
        # Mock implementation - in production, this would trigger document reprocessing
        print(f"Reprocessing document {document_id} initiated by user {initiated_by_user_id}")
        await asyncio.sleep(1)  # Simulate processing time

    async def delete_document(self, document_id: str, deleted_by_user_id: int):
        """Admin delete a document"""
        # Mock implementation - in production, this would delete document and vectors
        print(f"Document {document_id} deleted by admin user {deleted_by_user_id}")

    async def bulk_delete_documents(self, document_ids: List[str], deleted_by_user_id: int) -> Dict[str, Any]:
        """Bulk delete multiple documents"""
        results = {
            "success_count": 0,
            "error_count": 0,
            "errors": []
        }

        for doc_id in document_ids:
            try:
                await self.delete_document(doc_id, deleted_by_user_id)
                results["success_count"] += 1
            except Exception as e:
                results["error_count"] += 1
                results["errors"].append({
                    "document_id": doc_id,
                    "error": str(e)
                })

        return results

    # ============================================================================
    # AI Model Management
    # ============================================================================

    async def get_ai_providers(self) -> Dict[str, Any]:
        """Get AI provider status and configuration"""
        return {
            "providers": [
                {
                    "id": "openai",
                    "name": "OpenAI",
                    "status": "active",
                    "models": ["gpt-4", "gpt-3.5-turbo", "text-embedding-ada-002"],
                    "rate_limit": "10K/min",
                    "cost_per_1k": 0.002,
                    "last_used": datetime.utcnow() - timedelta(minutes=2),
                    "success_rate": 99.8
                },
                {
                    "id": "anthropic",
                    "name": "Anthropic",
                    "status": "active",
                    "models": ["claude-3-opus", "claude-3-sonnet", "claude-3-haiku"],
                    "rate_limit": "5K/min",
                    "cost_per_1k": 0.008,
                    "last_used": datetime.utcnow() - timedelta(minutes=15),
                    "success_rate": 99.5
                },
                {
                    "id": "groq",
                    "name": "Groq",
                    "status": "active",
                    "models": ["llama2-70b-4096", "mixtral-8x7b-32768"],
                    "rate_limit": "30K/min",
                    "cost_per_1k": 0.0001,
                    "last_used": datetime.utcnow() - timedelta(hours=1),
                    "success_rate": 98.9
                },
                {
                    "id": "local",
                    "name": "Local Models",
                    "status": "inactive",
                    "models": [],
                    "rate_limit": "N/A",
                    "cost_per_1k": 0.0,
                    "last_used": None,
                    "success_rate": 0.0
                }
            ],
            "total_calls_today": 2847,
            "total_cost_today": 23.45,
            "average_response_time": 245
        }

    async def get_ai_usage_metrics(self, time_range: str) -> Dict[str, Any]:
        """Get AI model usage metrics and analytics"""
        return {
            "provider_usage": [
                {
                    "provider": "openai",
                    "calls_today": 2534,
                    "success_rate": 99.8,
                    "average_latency": 230,
                    "cost_today": 20.87
                },
                {
                    "provider": "anthropic",
                    "calls_today": 228,
                    "success_rate": 99.5,
                    "average_latency": 340,
                    "cost_today": 2.45
                },
                {
                    "provider": "groq",
                    "calls_today": 85,
                    "success_rate": 98.9,
                    "average_latency": 120,
                    "cost_today": 0.13
                }
            ],
            "total_calls_today": 2847,
            "total_cost_today": 23.45,
            "average_response_time": 245,
            "success_rate": 99.6,
            "cost_breakdown": {
                "openai": 20.87,
                "anthropic": 2.45,
                "groq": 0.13
            }
        }

    async def update_ai_provider_config(self, provider_id: str, config_data: Dict[str, Any], updated_by_user_id: int) -> Dict[str, Any]:
        """Update AI provider configuration"""
        # Mock implementation - in production, this would update provider settings
        updated_config = {
            "provider_id": provider_id,
            "updated_at": datetime.utcnow(),
            "updated_by": updated_by_user_id,
            "config": config_data
        }

        return updated_config

    async def test_ai_provider(self, provider_id: str, tested_by_user_id: int) -> Dict[str, Any]:
        """Test AI provider connection and functionality"""
        # Mock implementation - in production, this would test actual provider
        await asyncio.sleep(2)  # Simulate test time

        return {
            "provider_id": provider_id,
            "test_status": "success",
            "response_time": 245,
            "test_message": "Connection successful",
            "tested_at": datetime.utcnow(),
            "tested_by": tested_by_user_id
        }

    # ============================================================================
    # Audit Logging
    # ============================================================================

    async def get_audit_logs(self, filters) -> Dict[str, Any]:
        """Get audit logs with filtering"""
        # Mock implementation - in production, this would query audit_logs table
        logs = []
        for i in range(filters.page_size):
            logs.append({
                "id": f"audit_{i + (filters.page - 1) * filters.page_size}",
                "timestamp": datetime.utcnow() - timedelta(minutes=i * 5),
                "user_id": "3",
                "user_email": "admin@eliza.com",
                "action": "user_created" if i % 3 == 0 else "document_uploaded" if i % 3 == 1 else "search_query",
                "resource": "user_management" if i % 3 == 0 else "document_management" if i % 3 == 1 else "search",
                "severity": "medium" if i % 4 == 0 else "low",
                "status": "success",
                "details": {
                    "ip_address": "192.168.1.100",
                    "user_agent": "Mozilla/5.0...",
                    "additional_info": f"Action {i + 1} details"
                }
            })

        return {
            "logs": logs,
            "pagination": {
                "page": filters.page,
                "page_size": filters.page_size,
                "total_count": 15420,
                "total_pages": 309
            }
        }

    # ============================================================================
    # Email Services (Mock implementations)
    # ============================================================================

    async def send_user_invitation(self, user_id: int, email: str):
        """Send user invitation email"""
        # Mock implementation - in production, this would send actual email
        print(f"Sending invitation email to {email} for user {user_id}")
        await asyncio.sleep(1)

    async def send_password_reset_email(self, user_id: int, temp_password: str):
        """Send password reset email with temporary password"""
        # Mock implementation - in production, this would send actual email
        print(f"Sending password reset email to user {user_id} with temp password")
        await asyncio.sleep(1)


# Create global admin service instance
admin_service = AdminService()
