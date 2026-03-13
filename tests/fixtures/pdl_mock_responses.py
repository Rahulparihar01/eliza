"""
Mock API responses for People Data Labs testing.

These responses match the EXACT format of PDL API v5 responses:
- 404 format captured from live API on 2025-10-09
- 200 format based on PDL API v5 documentation and field structure
  used in src/services/ingestion/transformers/pdl_transformer.py

All person records include fields that our transformer expects:
- Required: id, full_name
- Job: job_title, job_title_role, job_company_name, job_start_date
- Location: location_name, location_locality, location_region, location_country
- Contact: emails (list of objects), phone_numbers
- Additional: skills, education, linkedin_url, likelihood, last_updated
"""

# Sample person record matching our test query (job_title_role=engineer)
SAMPLE_PERSON_RECORD = {
    "id": "test_pdl_person_001",
    "full_name": "Jane Doe",
    "first_name": "Jane",
    "last_name": "Doe",
    "linkedin_url": "https://www.linkedin.com/in/janedoe",
    "facebook_url": None,
    "twitter_url": None,
    "github_url": "https://github.com/janedoe",
    "work_email": "jane.doe@example.com",
    "personal_emails": ["jane@gmail.com"],
    "mobile_phone": None,
    "industry": "computer software",
    "job_title": "Senior Software Engineer",
    "job_title_role": "engineer",
    "job_title_sub_role": "software engineer",
    "job_title_levels": ["senior"],
    "job_company_id": "company_123",
    "job_company_name": "Example Tech Corp",
    "job_company_website": "example-tech.com",
    "job_company_size": "1001-5000",
    "job_company_founded": 2010,
    "job_company_industry": "computer software",
    "job_company_linkedin_url": "https://www.linkedin.com/company/example-tech",
    "job_start_date": "2020-01",
    "job_summary": "Leading backend services development",
    "location_name": "San Francisco, California, United States",
    "location_locality": "San Francisco",
    "location_region": "California",
    "location_country": "United States",
    "location_continent": "North America",
    "linkedin_username": "janedoe",
    "linkedin_id": "123456789",
    "inferred_salary": None,
    "inferred_years_experience": 8,
    "summary": "Experienced software engineer with focus on distributed systems",
    "phone_numbers": [],
    "emails": [
        {
            "address": "jane.doe@example.com",
            "type": "professional"
        }
    ],
    "interests": ["machine learning", "cloud computing", "open source"],
    "skills": ["Python", "Go", "Kubernetes", "AWS", "PostgreSQL"],
    "experience": [
        {
            "company": {
                "name": "Example Tech Corp",
                "id": "company_123",
                "size": "1001-5000",
                "founded": 2010,
                "industry": "computer software"
            },
            "title": {
                "name": "Senior Software Engineer",
                "role": "engineer",
                "sub_role": "software engineer",
                "levels": ["senior"]
            },
            "start_date": "2020-01",
            "end_date": None,
            "is_primary": True
        },
        {
            "company": {
                "name": "Previous Startup",
                "id": "company_456",
                "size": "51-200",
                "founded": 2015,
                "industry": "internet"
            },
            "title": {
                "name": "Software Engineer",
                "role": "engineer",
                "sub_role": "software engineer"
            },
            "start_date": "2017-06",
            "end_date": "2019-12",
            "is_primary": False
        }
    ],
    "education": [
        {
            "school": {
                "name": "University of California, Berkeley",
                "type": "university"
            },
            "degrees": ["bachelor"],
            "majors": ["Computer Science"],
            "start_date": "2011",
            "end_date": "2015"
        }
    ],
    "profiles": [
        {
            "network": "linkedin",
            "id": "123456789",
            "url": "https://www.linkedin.com/in/janedoe",
            "username": "janedoe"
        },
        {
            "network": "github",
            "url": "https://github.com/janedoe",
            "username": "janedoe"
        }
    ],
    "likelihood": 8,  # PDL confidence score (1-10)
    "last_updated": "2024-10-01"  # ISO date when PDL last updated this record
}

# Second sample person for testing multiple records
SAMPLE_PERSON_RECORD_2 = {
    "id": "test_pdl_person_002",
    "full_name": "John Smith",
    "first_name": "John",
    "last_name": "Smith",
    "linkedin_url": "https://www.linkedin.com/in/johnsmith",
    "work_email": "john.smith@techcorp.com",
    "personal_emails": ["john@example.com"],
    "industry": "information technology and services",
    "job_title": "Staff Engineer",
    "job_title_role": "engineer",
    "job_title_sub_role": "software engineer",
    "job_title_levels": ["staff"],
    "job_company_name": "TechCorp Inc",
    "job_company_website": "techcorp.com",
    "location_name": "Seattle, Washington, United States",
    "location_locality": "Seattle",
    "location_region": "Washington",
    "location_country": "United States",
    "inferred_years_experience": 12,
    "skills": ["Java", "Spring", "Microservices", "Docker"],
    "phone_numbers": [],
    "education": [],
    "profiles": [],
    "likelihood": 7,
    "last_updated": "2024-09-15"
}

# Mock response for successful search with results
# Format matches actual PDL API v5 response structure
SEARCH_SUCCESS_RESPONSE = {
    "status": 200,
    "total": 2,
    "data": [SAMPLE_PERSON_RECORD, SAMPLE_PERSON_RECORD_2],
    "scroll_token": "mock_scroll_token_abc123"  # Token for next page
}

# Mock response for search with single result (for sample record)
# This matches what PDL returns for a query with 1 result
SEARCH_SINGLE_RESULT_RESPONSE = {
    "status": 200,
    "total": 1,
    "data": [SAMPLE_PERSON_RECORD]
    # No scroll_token when there are no more pages
}

# Mock response for search with no results (404)
# This is the EXACT format captured from real PDL API on 2025-10-09
SEARCH_NO_RESULTS_RESPONSE = {
    "status": 404,
    "error": {
        "type": "not_found",
        "message": "No records were found matching your search"
    },
    "total": 0
}

# Mock response for cost estimation (metadata endpoint)
COST_ESTIMATION_RESPONSE = {
    "status": 200,
    "total": 150,  # Estimated count
    "data": [SAMPLE_PERSON_RECORD]  # Single sample for preview
}

# Mock response for connection test (should return quickly)
CONNECTION_TEST_RESPONSE = {
    "status": 200,
    "total": 1,
    "data": [SAMPLE_PERSON_RECORD]
}

# Mock response for rate limit error
RATE_LIMIT_ERROR_RESPONSE = {
    "status": 429,
    "error": {
        "type": "rate_limit_error",
        "message": "Rate limit exceeded. Please wait before making more requests."
    }
}

# Mock response for auth error
AUTH_ERROR_RESPONSE = {
    "status": 401,
    "error": {
        "type": "authentication_error",
        "message": "Invalid API key"
    }
}

