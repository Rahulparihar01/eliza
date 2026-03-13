"""
People Data Labs Connector

Connector for People Data Labs Person Search API.
Supports query validation, cost estimation, and incremental syncs.

API Documentation: https://docs.peopledatalabs.com/docs/person-search-api
"""
from typing import Dict, Any, Iterator, List, Optional, Tuple
import requests
import time

from src.core.logging import get_logger, LogCategory
from src.core.config import get_settings
from .base import SimpleStreamConnector, ConnectorStatus
from ..rate_limiter import RateLimiter

logger = get_logger(__name__, LogCategory.BUSINESS)


class PDLQuotaExceededError(Exception):
    """Raised when PDL API quota/credits are exhausted."""
    
    def __init__(self, message: str = "PDL API quota exceeded"):
        self.message = message
        self.user_message = (
            "The People Data Labs API quota has been exceeded. "
            "Market candidate search is temporarily unavailable. "
            "Please contact your administrator to add more PDL credits, "
            "or try again later. Applicant/resume analysis can still proceed."
        )
        super().__init__(self.message)


class PDLAuthenticationError(Exception):
    """Raised when PDL API key is invalid."""
    
    def __init__(self, message: str = "Invalid PDL API key"):
        self.message = message
        self.user_message = (
            "The People Data Labs API key is invalid or expired. "
            "Please contact your administrator to update the API credentials."
        )
        super().__init__(self.message)


class PeopleDataLabsConnector(SimpleStreamConnector):
    """
    People Data Labs Person Search connector.
    
    Features:
    - Query validation with all PDL field types
    - Cost estimation (size=0 API call)
    - Rate limiting (60 req/min default, configurable)
    - Pagination with offset/size
    - Error handling (429, 401, 5xx)
    - Incremental sync support
    
    Configuration:
        credentials: {
            "api_key": str
        }
        config: {
            "search_query": dict,  # PDL query object
            "max_records": int,    # Optional limit
            "page_size": int,      # Records per page (default: 100)
            "rate_limit": int      # Requests per minute (default: 60)
        }
    
    Example Query:
        {
            "job_title_role": ["software engineer", "data scientist"],
            "job_company_name": ["Google", "Amazon"],
            "location_country": ["United States"],
            "skills": ["python", "machine learning"]
        }
    """
    
    BASE_URL = "https://api.peopledatalabs.com/v5"
    
    # Valid PDL query fields (for validation)
    VALID_QUERY_FIELDS = {
        # Job fields
        "job_title": (str, list),
        "job_title_role": (str, list),
        "job_title_sub_role": (str, list),
        "job_title_levels": (str, list),
        "job_company_name": (str, list),
        "job_company_website": (str, list),
        "job_company_size": (str, list),
        "job_company_industry": (str, list),
        "job_company_location_name": (str, list),
        
        # Location fields
        "location_name": (str, list),
        "location_locality": (str, list),
        "location_metro": (str, list),
        "location_region": (str, list),
        "location_country": (str, list),
        "location_continent": (str, list),
        
        # Education fields
        "education_school_name": (str, list),
        "education_school_type": (str, list),
        "education_degree_name": (str, list),
        "education_major": (str, list),
        
        # Contact fields
        "phone_numbers": (str, list),
        "emails": (str, list),
        
        # Skills & Experience
        "skills": (str, list),
        "experience_years_min": (int,),
        "experience_years_max": (int,),
        "inferred_salary_min": (int,),
        "inferred_salary_max": (int,),
        
        # Personal fields
        "first_name": (str,),
        "last_name": (str,),
        "birth_year_min": (int,),
        "birth_year_max": (int,),
        "languages": (str, list),
        
        # Social profiles
        "linkedin_url": (str,),
        "linkedin_username": (str,),
        "facebook_url": (str,),
        "twitter_url": (str,),
        "github_url": (str,),
    }
    
    def __init__(
        self,
        credentials: Dict[str, str],
        config: Dict[str, Any],
        customer_id: str
    ):
        """Initialize PDL connector."""
        super().__init__(credentials, config, customer_id)
        
        # Extract configuration
        self.api_key = credentials.get("api_key")
        if not self.api_key:
            raise ValueError("api_key is required in credentials")
        
        self.search_query = config.get("search_query", {})
        self.max_records = config.get("max_records", get_settings().max_connector_records_default)
        self.page_size = config.get("page_size", 100)
        
        # Initialize rate limiter
        rate_limit = config.get("rate_limit", get_settings().pdl_default_rate_limit)
        self.rate_limiter = RateLimiter(max_requests=rate_limit, time_window=60)
        
        logger.info(
            "pdl_connector_initialized",
            customer_id=customer_id,
            rate_limit=rate_limit,
            max_records=self.max_records
        )
    
    @property
    def stream_name(self) -> str:
        """Stream name for PDL person search."""
        return "person_search"
    
    @property
    def supported_sync_modes(self) -> List[str]:
        """PDL supports full refresh (no native incremental)."""
        return ["full"]
    
    def _convert_to_pdl_query(self, simple_query: Dict[str, Any]) -> Dict[str, Any]:
        """
        Convert simple key-value query to PDL Elasticsearch DSL format.
        
        Args:
            simple_query: {
                "job_title_role": ["software engineer"],
                "location_country": ["United States"]
            }
            
        Returns:
            PDL Elasticsearch DSL query:
            {
                "bool": {
                    "must": [
                        {"term": {"job_title_role": "software engineer"}},
                        {"term": {"location_country": "united states"}}
                    ]
                }
            }
        """
        if not simple_query:
            return {}
        
        must_clauses = []
        
        for field, values in simple_query.items():
            if not values:
                continue
            
            # Handle list values
            if isinstance(values, list):
                if len(values) == 1:
                    # Single value - use term query
                    must_clauses.append({
                        "term": {field: values[0].lower() if isinstance(values[0], str) else values[0]}
                    })
                else:
                    # Multiple values - use terms query  
                    must_clauses.append({
                        "terms": {field: [v.lower() if isinstance(v, str) else v for v in values]}
                    })
            else:
                # Single value
                must_clauses.append({
                    "term": {field: values.lower() if isinstance(values, str) else values}
                })
        
        if not must_clauses:
            return {}
        
        return {
            "bool": {
                "must": must_clauses
            }
        }
    
    def check(self) -> Dict[str, Any]:
        """
        Test PDL API connection and credentials.
        
        Makes a minimal API call to verify:
        - API key is valid
        - API is reachable
        - Rate limit info (from headers)
        """
        try:
            self.rate_limiter.acquire()
            
            # Minimal query to test connection
            response = requests.post(
                f"{self.BASE_URL}/person/search",
                headers={
                    "X-Api-Key": self.api_key,
                    "Content-Type": "application/json"
                },
                json={
                    # PDL Elasticsearch DSL format
                    "query": {
                        "bool": {
                            "must": [
                                {"term": {"location_country": "united states"}}
                            ]
                        }
                    },
                    "size": 1  # Minimal response
                },
                timeout=10
            )
            
            if response.status_code == 200:
                data = response.json()
                
                # Extract rate limit info from headers
                rate_limit_remaining = response.headers.get("X-RateLimit-Remaining")
                rate_limit_limit = response.headers.get("X-RateLimit-Limit")
                
                return {
                    "status": ConnectorStatus.HEALTHY,
                    "message": "Connected to PDL API successfully",
                    "metadata": {
                        "api_version": "v5",
                        "rate_limit_remaining": rate_limit_remaining,
                        "rate_limit_total": rate_limit_limit,
                        "total_records_available": data.get("total", 0)
                    }
                }
            elif response.status_code == 401:
                return {
                    "status": ConnectorStatus.UNHEALTHY,
                    "message": "Invalid API key",
                    "metadata": {"status_code": 401}
                }
            elif response.status_code == 429:
                return {
                    "status": ConnectorStatus.DEGRADED,
                    "message": "Rate limit exceeded",
                    "metadata": {"status_code": 429}
                }
            else:
                return {
                    "status": ConnectorStatus.UNHEALTHY,
                    "message": f"API error: {response.status_code}",
                    "metadata": {
                        "status_code": response.status_code,
                        "response": response.text[:200]
                    }
                }
                
        except requests.exceptions.Timeout:
            return {
                "status": ConnectorStatus.UNHEALTHY,
                "message": "API request timed out",
                "metadata": {"error": "timeout"}
            }
        except requests.exceptions.ConnectionError as e:
            return {
                "status": ConnectorStatus.UNHEALTHY,
                "message": "Cannot connect to PDL API",
                "metadata": {"error": str(e)}
            }
        except Exception as e:
            logger.error(f"PDL check failed: {e}", exc_info=True)
            return {
                "status": ConnectorStatus.UNHEALTHY,
                "message": f"Connection test failed: {str(e)}",
                "metadata": {"error": str(e)}
            }
    
    def get_stream_schema(self) -> Dict[str, Any]:
        """
        Return JSON schema for PDL person records.
        
        Based on PDL API documentation.
        """
        return {
            "type": "object",
            "properties": {
                "id": {"type": "string", "description": "PDL person ID"},
                "full_name": {"type": "string"},
                "first_name": {"type": "string"},
                "last_name": {"type": "string"},
                "middle_name": {"type": "string"},
                
                # Job info
                "job_title": {"type": "string"},
                "job_title_role": {"type": "string"},
                "job_title_sub_role": {"type": "string"},
                "job_title_levels": {"type": "array", "items": {"type": "string"}},
                "job_company_name": {"type": "string"},
                "job_company_id": {"type": "string"},
                "job_company_size": {"type": "string"},
                "job_company_industry": {"type": "string"},
                "job_start_date": {"type": "string"},
                
                # Contact
                "emails": {"type": "array", "items": {"type": "string"}},
                "phone_numbers": {"type": "array", "items": {"type": "string"}},
                "linkedin_url": {"type": "string"},
                "linkedin_username": {"type": "string"},
                "twitter_url": {"type": "string"},
                "github_url": {"type": "string"},
                
                # Location
                "location_name": {"type": "string"},
                "location_locality": {"type": "string"},
                "location_metro": {"type": "string"},
                "location_region": {"type": "string"},
                "location_country": {"type": "string"},
                "location_continent": {"type": "string"},
                
                # Skills & Education
                "skills": {"type": "array", "items": {"type": "string"}},
                "inferred_years_experience": {"type": "integer"},
                "education": {"type": "array", "items": {"type": "object"}},
                "experience": {"type": "array", "items": {"type": "object"}},
                
                # Metadata
                "likelihood": {"type": "integer", "minimum": 1, "maximum": 10},
                "last_updated": {"type": "string", "format": "date-time"}
            },
            "required": ["id"]
        }
    
    def validate_config(self) -> Tuple[bool, str]:
        """
        Validate PDL query configuration.
        
        Checks:
        - search_query is present
        - At least one search criterion
        - All fields are valid PDL fields
        - Field types match expected types
        """
        # Check search_query exists
        if not self.search_query:
            return False, "search_query is required in config"
        
        if not isinstance(self.search_query, dict):
            return False, "search_query must be a dictionary"
        
        # Check at least one criterion
        if not self.search_query:
            return False, "search_query must contain at least one search criterion"
        
        # Validate each field
        for field, value in self.search_query.items():
            # Check field is valid
            if field not in self.VALID_QUERY_FIELDS:
                valid_fields = ", ".join(list(self.VALID_QUERY_FIELDS.keys())[:10])
                return False, f"Invalid field '{field}'. Valid fields include: {valid_fields}..."
            
            # Check value type
            expected_types = self.VALID_QUERY_FIELDS[field]
            if not isinstance(value, expected_types):
                type_names = " or ".join([t.__name__ for t in expected_types])
                return False, f"Field '{field}' must be {type_names}, got {type(value).__name__}"
        
        # All validation passed
        return True, ""
    
    def estimate_record_count(self, query_params: Optional[Dict[str, Any]] = None) -> Optional[int]:
        """
        Estimate number of records for a query.
        
        Makes API call with size=0 to get total count without fetching records.
        
        Args:
            query_params: Query to estimate (defaults to self.search_query)
            
        Returns:
            Estimated record count
        """
        query = query_params or self.search_query
        
        if not query:
            return None
        
        try:
            self.rate_limiter.acquire()
            
            # Convert simple query to PDL Elasticsearch DSL
            pdl_query = self._convert_to_pdl_query(query)
            
            response = requests.post(
                f"{self.BASE_URL}/person/search",
                headers={
                    "X-Api-Key": self.api_key,
                    "Content-Type": "application/json"
                },
                json={
                    "query": pdl_query,
                    "size": 1  # Minimal size (PDL requires 1-100)
                },
                timeout=10
            )
            
            if response.status_code == 200:
                data = response.json()
                total = data.get("total", 0)
                
                logger.info(
                    "pdl_estimate_complete",
                    customer_id=self.customer_id,
                    estimated_count=total
                )
                
                return total
            elif response.status_code == 404:
                # 404 from PDL means no records found, which is 0 count
                data = response.json()
                if data.get("error", {}).get("type") == "not_found":
                    logger.info(
                        "pdl_estimate_zero_results",
                        customer_id=self.customer_id,
                        estimated_count=0
                    )
                    return 0
                else:
                    logger.warning(
                        "pdl_estimate_failed",
                        status_code=response.status_code,
                        response=response.text[:200]
                    )
                    return None
            else:
                logger.warning(
                    "pdl_estimate_failed",
                    status_code=response.status_code,
                    response=response.text[:200]
                )
                return None
                
        except Exception as e:
            logger.error(f"Failed to estimate record count: {e}", exc_info=True)
            return None
    
    def get_sample_record(self, stream_name: str = "person_search") -> Optional[Dict[str, Any]]:
        """
        Fetch a single sample record from the PDL API.
        
        Used for schema discovery and validation.
        
        Args:
            stream_name: Name of the stream (ignored for PDL, always uses person search)
            
        Returns:
            A single person record, or None if fetch fails
        """
        try:
            # Convert simple query to PDL Elasticsearch DSL
            pdl_query = self._convert_to_pdl_query(self.search_query)
            
            # Build search request
            request_data = {
                "query": pdl_query,
                "size": 1,  # Only fetch 1 record
                "pretty": True
            }
            
            # Construct endpoint URL and headers
            search_url = f"{self.BASE_URL}/person/search"
            headers = {
                "X-Api-Key": self.api_key,
                "Content-Type": "application/json"
            }
            
            # Make API call with rate limiting
            self.rate_limiter.acquire()
            
            response = requests.post(
                search_url,
                headers=headers,
                json=request_data,
                timeout=30
            )
            
            if response.status_code == 200:
                data = response.json()
                records = data.get("data", [])
                
                if records:
                    logger.info(
                        "sample_record_fetched",
                        record_id=records[0].get("id", "unknown"),
                        fields_count=len(records[0])
                    )
                    return records[0]
                else:
                    logger.warning("No sample records found for query")
                    return None
            elif response.status_code == 404:
                # 404 from PDL means no records match the query
                logger.info(
                    "sample_record_no_matches",
                    customer_id=self.customer_id
                )
                return None
            else:
                logger.error(
                    "sample_record_fetch_failed",
                    status_code=response.status_code,
                    error=response.text[:200]
                )
                return None
                
        except Exception as e:
            logger.error(f"Failed to fetch sample record: {e}", exc_info=True)
            return None
    
    def read_stream(
        self,
        sync_mode: str,
        sync_params: Dict[str, Any]
    ) -> Iterator[List[Dict[str, Any]]]:
        """
        Stream person records from PDL API.
        
        Handles:
        - Pagination with offset/size
        - Rate limiting
        - Error handling and retries
        - Max record limit
        
        Args:
            sync_mode: "full" (incremental not supported by PDL)
            sync_params: {
                "checkpoint": {"offset": int},  # For resuming
                "max_records": int              # Optional override
            }
        
        Yields:
            Batches of person records
        """
        # Extract parameters
        checkpoint = sync_params.get("checkpoint", {})
        start_offset = checkpoint.get("offset", 0)
        max_records = sync_params.get("max_records", self.max_records)
        
        logger.info(
            "pdl_sync_starting",
            customer_id=self.customer_id,
            start_offset=start_offset,
            max_records=max_records,
            query_fields=list(self.search_query.keys())
        )
        
        offset = start_offset
        records_fetched = 0
        consecutive_errors = 0
        max_errors = 5
        scroll_token = None  # PDL uses scroll token for pagination
        
        while records_fetched < max_records:
            # Rate limiting
            self.rate_limiter.acquire()
            
            try:
                # Calculate page size for this request
                remaining = max_records - records_fetched
                current_page_size = min(self.page_size, remaining)
                
                # Convert simple query to PDL Elasticsearch DSL
                pdl_query = self._convert_to_pdl_query(self.search_query)
                
                # Build request body
                request_body = {
                    "query": pdl_query,
                    "size": current_page_size
                }
                
                # Add scroll_token if we have one (for pagination after first request)
                if scroll_token:
                    request_body["scroll_token"] = scroll_token
                
                # Make API request
                response = requests.post(
                    f"{self.BASE_URL}/person/search",
                    headers={
                        "X-Api-Key": self.api_key,
                        "Content-Type": "application/json"
                    },
                    json=request_body,
                    timeout=30
                )
                
                # Handle response
                if response.status_code == 200:
                    data = response.json()
                    records = data.get("data", [])
                    total = data.get("total", 0)
                    scroll_token = data.get("scroll_token")  # Get scroll token for next page
                    
                    if not records:
                        logger.info(
                            "pdl_sync_complete_no_more_records",
                            records_fetched=records_fetched,
                            total=total
                        )
                        break
                    
                    # Yield batch
                    yield records
                    
                    records_fetched += len(records)
                    consecutive_errors = 0  # Reset error counter
                    
                    logger.debug(
                        "pdl_page_fetched",
                        page_size=len(records),
                        records_fetched=records_fetched,
                        total=total,
                        has_more=bool(scroll_token)
                    )
                    
                    # If no scroll token, we've reached the end
                    if not scroll_token:
                        logger.info(
                            "pdl_sync_complete_no_scroll_token",
                            records_fetched=records_fetched,
                            total=total
                        )
                        break
                
                elif response.status_code == 429:
                    # Rate limit exceeded - wait and retry
                    retry_after = int(response.headers.get("Retry-After", 60))
                    logger.warning(
                        "pdl_rate_limit_hit",
                        retry_after=retry_after,
                        records_fetched=records_fetched
                    )
                    time.sleep(retry_after)
                    continue
                
                elif response.status_code == 401:
                    raise PDLAuthenticationError("Invalid or expired PDL API key")
                
                elif response.status_code == 402:
                    # Payment required - quota exceeded
                    error_data = response.json() if response.text else {}
                    error_message = error_data.get("error", {}).get("message", "PDL API quota exceeded")
                    logger.warning(
                        "pdl_quota_exceeded",
                        customer_id=self.customer_id,
                        records_fetched=records_fetched,
                        error_message=error_message
                    )
                    raise PDLQuotaExceededError(f"PDL API quota exceeded: {error_message}")
                
                elif response.status_code == 404:
                    # No records found - treat as successful completion with 0 results
                    logger.info(
                        "pdl_sync_complete_no_matching_records",
                        records_fetched=records_fetched,
                        note="No records found matching search criteria"
                    )
                    break
                
                elif response.status_code >= 500:
                    # Server error - retry with backoff
                    consecutive_errors += 1
                    if consecutive_errors >= max_errors:
                        raise Exception(f"Too many server errors ({consecutive_errors})")
                    
                    backoff = min(60, 2 ** consecutive_errors)
                    logger.warning(
                        "pdl_server_error_retrying",
                        status_code=response.status_code,
                        backoff=backoff,
                        attempt=consecutive_errors
                    )
                    time.sleep(backoff)
                    continue
                
                else:
                    raise Exception(f"API error: {response.status_code} - {response.text[:200]}")
            
            except requests.exceptions.Timeout:
                consecutive_errors += 1
                if consecutive_errors >= max_errors:
                    raise Exception("Too many timeouts")
                
                logger.warning("pdl_request_timeout_retrying", attempt=consecutive_errors)
                time.sleep(5)
                continue
            
            except Exception as e:
                logger.error(
                    "pdl_sync_error",
                    error=str(e),
                    offset=offset,
                    records_fetched=records_fetched,
                    exc_info=True
                )
                raise
        
        logger.info(
            "pdl_sync_complete",
            customer_id=self.customer_id,
            records_fetched=records_fetched,
            final_offset=offset
        )
    
    def create_checkpoint(
        self,
        records_synced: int,
        last_record: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Create checkpoint for resuming sync.
        
        PDL uses offset-based pagination.
        """
        return {
            "offset": records_synced,
            "timestamp": time.time()
        }

