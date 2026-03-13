"""
Pytest configuration and fixtures for testing.

This file sets up mock API responses to avoid hitting rate limits
and ensure deterministic testing.
"""

import json
import pytest
import responses
from tests.fixtures.pdl_mock_responses import (
    SEARCH_SUCCESS_RESPONSE,
    SEARCH_SINGLE_RESULT_RESPONSE,
    SEARCH_NO_RESULTS_RESPONSE,
    COST_ESTIMATION_RESPONSE,
    CONNECTION_TEST_RESPONSE,
    RATE_LIMIT_ERROR_RESPONSE,
    AUTH_ERROR_RESPONSE
)


@pytest.fixture(scope="function")
def mock_pdl_api():
    """
    Mock all PDL API endpoints with realistic responses.
    
    This fixture intercepts HTTP requests to the PDL API and returns
    mock responses based on the request parameters.
    """
    with responses.RequestsMock(assert_all_requests_are_fired=False) as rsps:
        # Default successful search response
        rsps.add(
            responses.POST,
            "https://api.peopledatalabs.com/v5/person/search",
            json=SEARCH_SINGLE_RESULT_RESPONSE,
            status=200
        )
        
        yield rsps


@pytest.fixture(scope="function")
def mock_pdl_api_no_results():
    """
    Mock PDL API to return no results (404).
    
    Useful for testing scenarios where the search query
    doesn't match any records.
    """
    with responses.RequestsMock(assert_all_requests_are_fired=False) as rsps:
        rsps.add(
            responses.POST,
            "https://api.peopledatalabs.com/v5/person/search",
            json=SEARCH_NO_RESULTS_RESPONSE,
            status=404
        )
        
        yield rsps


@pytest.fixture(scope="function")
def mock_pdl_api_rate_limit():
    """
    Mock PDL API to return rate limit error.
    
    Useful for testing rate limit handling and retry logic.
    """
    with responses.RequestsMock(assert_all_requests_are_fired=False) as rsps:
        rsps.add(
            responses.POST,
            "https://api.peopledatalabs.com/v5/person/search",
            json=RATE_LIMIT_ERROR_RESPONSE,
            status=429,
            headers={"Retry-After": "60"}
        )
        
        yield rsps


@pytest.fixture(scope="function")
def mock_pdl_api_multiple_records():
    """
    Mock PDL API to return multiple records (pagination).
    
    Useful for testing batch processing and pagination logic.
    """
    with responses.RequestsMock(assert_all_requests_are_fired=False) as rsps:
        rsps.add(
            responses.POST,
            "https://api.peopledatalabs.com/v5/person/search",
            json=SEARCH_SUCCESS_RESPONSE,
            status=200
        )
        
        yield rsps

