"""
Authentication and authorization for the AI Enablement Platform.
Simple customer-based authentication for Phase 2.
"""

import logging
from typing import Optional
from fastapi import HTTPException, Header, status

logger = logging.getLogger(__name__)


async def get_current_customer_id(
    x_customer_id: Optional[str] = Header(None, description="Customer ID for multi-tenant access")
) -> str:
    """
    Simple customer authentication using header.

    In Phase 2, we use a simple header-based authentication.
    In later phases, this will be replaced with proper JWT/OAuth.
    """

    if not x_customer_id:
        # Require customer ID to be provided
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Customer ID header (X-Customer-Id) is required"
        )

    # Basic validation
    if len(x_customer_id) < 3 or len(x_customer_id) > 50:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid customer ID format"
        )

    # TODO: In production, validate customer exists in database
    # For now, accept any reasonable customer ID

    return x_customer_id


async def get_optional_customer_id(
    x_customer_id: Optional[str] = Header(None, description="Customer ID for multi-tenant access")
) -> Optional[str]:
    """
    Optional customer authentication - returns None if not provided.
    """
    
    if not x_customer_id:
        return None
    
    try:
        return await get_current_customer_id(x_customer_id)
    except HTTPException:
        return None


# TODO: Implement proper authentication in later phases
# - JWT token validation
# - User session management
# - Role-based access control
# - API key authentication
