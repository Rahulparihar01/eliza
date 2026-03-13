"""
Pydantic schemas for Admin API endpoints.
Defines request/response models for dashboard, metrics, and system health.
"""

from pydantic import BaseModel, Field
from typing import List, Dict, Optional, Any
from datetime import datetime


# ============================================================================
# System Health Schemas
# ============================================================================

class SystemHealthStatus(BaseModel):
    """System health status details"""
    api_status: str = Field(..., description="API service status: online, degraded, offline")
    database_status: str = Field(..., description="Database connection status: healthy, slow, error")
    vector_service_status: str = Field(..., description="Vector service status: operational, degraded, down")
    redis_status: str = Field(..., description="Redis connection status: connected, disconnected")
    neo4j_status: str = Field(..., description="Neo4j connection status: available, unavailable")
    last_health_check: datetime = Field(..., description="Last health check timestamp")
    uptime_percentage: float = Field(..., ge=0, le=100, description="System uptime percentage")

    class Config:
        json_schema_extra = {
            "example": {
                "api_status": "online",
                "database_status": "healthy",
                "vector_service_status": "operational",
                "redis_status": "connected",
                "neo4j_status": "available",
                "last_health_check": "2025-10-01T12:00:00Z",
                "uptime_percentage": 99.9
            }
        }


# ============================================================================
# User Activity Schemas
# ============================================================================

class UserActivityMetrics(BaseModel):
    """User activity metrics"""
    active_users_now: int = Field(..., ge=0, description="Currently active users (sessions in last 15 min)")
    active_users_today: int = Field(..., ge=0, description="Active users today")
    total_registered_users: int = Field(..., ge=0, description="Total registered users")
    new_users_this_week: int = Field(..., ge=0, description="New users registered this week")
    user_growth_percentage: float = Field(..., description="User growth percentage (week over week)")

    class Config:
        json_schema_extra = {
            "example": {
                "active_users_now": 23,
                "active_users_today": 67,
                "total_registered_users": 156,
                "new_users_this_week": 12,
                "user_growth_percentage": 15.2
            }
        }


# ============================================================================
# Document Metrics Schemas
# ============================================================================

class DocumentMetrics(BaseModel):
    """Document processing metrics"""
    total_documents: int = Field(..., ge=0, description="Total documents in system")
    documents_uploaded_today: int = Field(..., ge=0, description="Documents uploaded today")
    total_searches_today: int = Field(..., ge=0, description="Total searches performed today")
    processing_queue_size: int = Field(..., ge=0, description="Current processing queue size")
    storage_usage_gb: float = Field(..., ge=0, description="Storage usage in gigabytes")

    class Config:
        json_schema_extra = {
            "example": {
                "total_documents": 1247,
                "documents_uploaded_today": 45,
                "total_searches_today": 892,
                "processing_queue_size": 12,
                "storage_usage_gb": 15.2
            }
        }


# ============================================================================
# AI Usage Schemas
# ============================================================================

class AIUsageMetrics(BaseModel):
    """AI model usage metrics"""
    total_calls_today: int = Field(..., ge=0, description="Total AI API calls today")
    total_cost_today: float = Field(..., ge=0, description="Total cost today in USD")
    average_response_time: float = Field(..., ge=0, description="Average response time in milliseconds")
    success_rate: float = Field(..., ge=0, le=100, description="Success rate percentage")
    provider_breakdown: Dict[str, float] = Field(
        default_factory=dict,
        description="Usage percentage by AI provider"
    )

    class Config:
        json_schema_extra = {
            "example": {
                "total_calls_today": 2847,
                "total_cost_today": 23.45,
                "average_response_time": 245.5,
                "success_rate": 99.8,
                "provider_breakdown": {
                    "openai": 89.0,
                    "anthropic": 8.0,
                    "groq": 3.0
                }
            }
        }


# ============================================================================
# Recent Activity Schemas
# ============================================================================

class RecentActivityItem(BaseModel):
    """Recent activity log item"""
    timestamp: datetime = Field(..., description="Activity timestamp")
    action: str = Field(..., description="Action performed")
    details: str = Field(..., description="Activity details")

    class Config:
        json_schema_extra = {
            "example": {
                "timestamp": "2025-10-01T10:30:00Z",
                "action": "User created",
                "details": "New user registered: sarah@company.com"
            }
        }


# ============================================================================
# Dashboard Overview Schema
# ============================================================================

class DashboardOverviewResponse(BaseModel):
    """Complete admin dashboard overview response"""
    system_health: SystemHealthStatus = Field(..., description="System health status")
    user_activity: UserActivityMetrics = Field(..., description="User activity metrics")
    document_metrics: DocumentMetrics = Field(..., description="Document processing metrics")
    ai_usage: AIUsageMetrics = Field(..., description="AI model usage metrics")
    recent_activity: List[RecentActivityItem] = Field(
        default_factory=list,
        description="Recent platform activity"
    )

    class Config:
        json_schema_extra = {
            "example": {
                "system_health": {
                    "api_status": "online",
                    "database_status": "healthy",
                    "vector_service_status": "operational",
                    "redis_status": "connected",
                    "neo4j_status": "available",
                    "last_health_check": "2025-10-01T12:00:00Z",
                    "uptime_percentage": 99.9
                },
                "user_activity": {
                    "active_users_now": 23,
                    "active_users_today": 67,
                    "total_registered_users": 156,
                    "new_users_this_week": 12,
                    "user_growth_percentage": 15.2
                },
                "document_metrics": {
                    "total_documents": 1247,
                    "documents_uploaded_today": 45,
                    "total_searches_today": 892,
                    "processing_queue_size": 12,
                    "storage_usage_gb": 15.2
                },
                "ai_usage": {
                    "total_calls_today": 2847,
                    "total_cost_today": 23.45,
                    "average_response_time": 245.5,
                    "success_rate": 99.8,
                    "provider_breakdown": {
                        "openai": 89.0,
                        "anthropic": 8.0,
                        "groq": 3.0
                    }
                },
                "recent_activity": []
            }
        }

