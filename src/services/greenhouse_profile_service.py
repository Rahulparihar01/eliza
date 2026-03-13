"""
Greenhouse Profile URL Service

Service to fetch and construct Greenhouse candidate profile URLs.
Uses the Greenhouse Harvest API to retrieve candidate information and profile URLs.
"""
import logging
import requests
import base64
from typing import Optional, Dict, Any
from sqlalchemy.orm import Session

from src.core.logging import get_logger, LogCategory
from src.models.connector import ConnectorConfiguration

logger = get_logger(__name__, LogCategory.INTEGRATION)


class GreenhouseProfileService:
    """Service for fetching Greenhouse candidate profile URLs."""
    
    BASE_URL = "https://harvest.greenhouse.io/v1"
    
    def __init__(self, db: Session, customer_id: str):
        """
        Initialize Greenhouse Profile Service.
        
        Args:
            db: Database session
            customer_id: Customer ID to find Greenhouse connector
        """
        self.db = db
        self.customer_id = customer_id
        self.api_key = None
        self._load_credentials()
    
    def _load_credentials(self) -> None:
        """Load Greenhouse API credentials from connector configuration."""
        try:
            from src.services.ingestion.connector_service import ConnectorService
            
            # Find active Greenhouse connector for this customer
            connector = self.db.query(ConnectorConfiguration).filter(
                ConnectorConfiguration.customer_id == self.customer_id,
                ConnectorConfiguration.connector_type == "greenhouse",
                ConnectorConfiguration.is_enabled == True
            ).first()
            
            if connector:
                # Use ConnectorService to get decrypted credentials
                connector_service = ConnectorService(self.db)
                credentials = connector_service.get_credentials(connector)
                self.api_key = credentials.get("api_key")
                
                if not self.api_key:
                    logger.warning(
                        "greenhouse_connector_missing_api_key",
                        customer_id=self.customer_id,
                        connector_id=connector.connector_id
                    )
        except Exception as e:
            logger.error(
                "greenhouse_credentials_load_error",
                customer_id=self.customer_id,
                error=str(e),
                exc_info=True
            )
    
    def _get_auth_headers(self) -> Dict[str, str]:
        """Get Basic Auth headers for Greenhouse API."""
        if not self.api_key:
            raise ValueError("Greenhouse API key not configured")
        
        credential = base64.b64encode(f"{self.api_key}:".encode()).decode()
        return {
            "Authorization": f"Basic {credential}",
            "Content-Type": "application/json"
        }
    
    def get_candidate_profile_url(
        self,
        candidate_id: int,
        email: Optional[str] = None
    ) -> Optional[str]:
        """
        Get Greenhouse profile URL for a candidate.
        
        Args:
            candidate_id: Greenhouse candidate ID
            email: Optional email address to search by if candidate_id not available
            
        Returns:
            Profile URL if found, None otherwise
        """
        if not self.api_key:
            logger.debug(
                "greenhouse_api_key_not_configured",
                customer_id=self.customer_id
            )
            return None
        
        try:
            # Try to fetch candidate by ID first
            if candidate_id:
                url = f"{self.BASE_URL}/candidates/{candidate_id}"
                headers = self._get_auth_headers()
                
                response = requests.get(url, headers=headers, timeout=10)
                
                if response.status_code == 200:
                    candidate_data = response.json()
                    # Extract profile URL from applications
                    if candidate_data.get("applications"):
                        for app in candidate_data["applications"]:
                            if app.get("profile_url"):
                                logger.info(
                                    "greenhouse_profile_url_fetched",
                                    candidate_id=candidate_id,
                                    profile_url=app["profile_url"]
                                )
                                return app["profile_url"]
                    
                    # If no profile_url in applications, construct it
                    # Format: https://app.greenhouse.io/people/{candidate_id}
                    # We need the board token, but we can construct a basic URL
                    # The actual URL format may vary by organization
                    profile_url = f"https://app.greenhouse.io/people/{candidate_id}"
                    logger.info(
                        "greenhouse_profile_url_constructed",
                        candidate_id=candidate_id,
                        profile_url=profile_url
                    )
                    return profile_url
                
                elif response.status_code == 404:
                    logger.debug(
                        "greenhouse_candidate_not_found",
                        candidate_id=candidate_id
                    )
                    return None
                else:
                    logger.warning(
                        "greenhouse_api_error",
                        candidate_id=candidate_id,
                        status_code=response.status_code,
                        response=response.text[:200]
                    )
                    return None
            
            # If no candidate_id but we have email, search for candidate
            elif email:
                # Search candidates by email
                url = f"{self.BASE_URL}/candidates"
                headers = self._get_auth_headers()
                params = {"email": email}
                
                response = requests.get(url, headers=headers, params=params, timeout=10)
                
                if response.status_code == 200:
                    candidates = response.json()
                    if candidates and len(candidates) > 0:
                        # Use first matching candidate
                        candidate = candidates[0]
                        candidate_id = candidate.get("id")
                        if candidate_id:
                            return self.get_candidate_profile_url(candidate_id)
            
            return None
            
        except requests.exceptions.RequestException as e:
            logger.error(
                "greenhouse_api_request_error",
                candidate_id=candidate_id,
                email=email,
                error=str(e),
                exc_info=True
            )
            return None
        except Exception as e:
            logger.error(
                "greenhouse_profile_url_error",
                candidate_id=candidate_id,
                email=email,
                error=str(e),
                exc_info=True
            )
            return None
    
    def find_candidate_by_email(self, email: str) -> Optional[Dict[str, Any]]:
        """
        Find Greenhouse candidate by email address.
        
        Note: Greenhouse Harvest API doesn't support direct email search.
        This method attempts to find candidates by paginating through results.
        For better performance, use candidate_id directly when available.
        
        Args:
            email: Candidate email address
            
        Returns:
            Candidate data dict with id and profile_url if found, None otherwise
        """
        if not self.api_key:
            return None
        
        try:
            # Greenhouse API doesn't support email search directly
            # We need to paginate through candidates and check emails
            # This is inefficient, so we limit to first 5 pages (500 candidates)
            url = f"{self.BASE_URL}/candidates"
            headers = self._get_auth_headers()
            
            # Search through first few pages
            for page in range(1, 6):  # Check first 5 pages
                params = {"page": page, "per_page": 100}
                
                response = requests.get(url, headers=headers, params=params, timeout=10)
                
                if response.status_code == 200:
                    candidates = response.json()
                    if not candidates:
                        break  # No more candidates
                    
                    # Check each candidate's email addresses
                    for candidate in candidates:
                        email_addresses = candidate.get("email_addresses", [])
                        for email_obj in email_addresses:
                            if email_obj.get("value", "").lower() == email.lower():
                                candidate_id = candidate.get("id")
                                profile_url = self.get_candidate_profile_url(candidate_id)
                                
                                # Extract LinkedIn URL
                                linkedin_url = None
                                for sm in candidate.get("social_media_addresses", []):
                                    if sm.get("type", "").lower() == "linkedin":
                                        linkedin_url = sm.get("value")
                                        break
                                
                                # Extract phone
                                phone = None
                                phone_numbers = candidate.get("phone_numbers", [])
                                if phone_numbers:
                                    phone = phone_numbers[0].get("value")
                                
                                # Extract location
                                location = None
                                addresses = candidate.get("addresses", [])
                                if addresses:
                                    addr = addresses[0]
                                    parts = []
                                    if addr.get("city"):
                                        parts.append(addr["city"])
                                    if addr.get("state"):
                                        parts.append(addr["state"])
                                    if addr.get("country"):
                                        parts.append(addr["country"])
                                    location = ", ".join(parts) if parts else None
                                
                                # Extract current employment
                                current_title = None
                                current_company = None
                                employments = candidate.get("employments", [])
                                if employments:
                                    current_title = employments[0].get("title")
                                    current_company = employments[0].get("company_name")
                                
                                return {
                                    "id": candidate_id,
                                    "profile_url": profile_url,
                                    "name": f"{candidate.get('first_name', '')} {candidate.get('last_name', '')}".strip(),
                                    "linkedin_url": linkedin_url,
                                    "phone": phone,
                                    "location": location,
                                    "current_title": current_title,
                                    "current_company": current_company,
                                    "data": candidate
                                }
                else:
                    logger.warning(
                        "greenhouse_search_error",
                        page=page,
                        status_code=response.status_code
                    )
                    break
            
            return None
            
        except Exception as e:
            logger.error(
                "greenhouse_find_candidate_error",
                email=email,
                error=str(e),
                exc_info=True
            )
            return None

