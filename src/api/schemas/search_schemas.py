"""
API schemas for person search endpoints.

Defines request/response models for search operations.
"""
from typing import List, Optional, Dict, Any
from pydantic import BaseModel, Field


# ==================== Request Schemas ====================

class PersonSearchRequest(BaseModel):
    """Request schema for person search."""
    query: str = Field(..., description="Search query text")
    filters: Optional[Dict[str, Any]] = Field(
        default=None,
        description="Optional filters (company, title, skills, location, min_experience)"
    )
    size: int = Field(default=10, ge=1, le=100, description="Number of results to return")
    from_: int = Field(default=0, ge=0, alias="from", description="Offset for pagination")
    
    class Config:
        json_schema_extra = {
            "example": {
                "query": "senior data engineer python",
                "filters": {
                    "company": "Netflix",
                    "skills": ["Python", "Spark"],
                    "min_experience": 5
                },
                "size": 10,
                "from": 0
            }
        }


class SkillSearchRequest(BaseModel):
    """Request schema for skill-based search."""
    skills: List[str] = Field(..., description="List of required skills")
    min_match: int = Field(
        default=1,
        ge=1,
        description="Minimum number of skills that must match"
    )
    size: int = Field(default=10, ge=1, le=100, description="Number of results")
    
    class Config:
        json_schema_extra = {
            "example": {
                "skills": ["Python", "Machine Learning", "AWS"],
                "min_match": 2,
                "size": 10
            }
        }


class CareerTransitionRequest(BaseModel):
    """Request schema for career transition query."""
    from_company: str = Field(..., description="Starting company")
    to_company: str = Field(..., description="Destination company")
    limit: int = Field(default=20, ge=1, le=100, description="Maximum results")
    
    class Config:
        json_schema_extra = {
            "example": {
                "from_company": "Microsoft",
                "to_company": "Netflix",
                "limit": 20
            }
        }


class CompanyNetworkRequest(BaseModel):
    """Request schema for company network query."""
    company_name: str = Field(..., description="Company to analyze")
    max_hops: int = Field(
        default=2,
        ge=1,
        le=3,
        description="Maximum relationship depth"
    )
    limit: int = Field(default=50, ge=1, le=200, description="Maximum companies")
    
    class Config:
        json_schema_extra = {
            "example": {
                "company_name": "Netflix",
                "max_hops": 2,
                "limit": 50
            }
        }


class SkillCooccurrenceRequest(BaseModel):
    """Request schema for skill co-occurrence analysis."""
    skill: str = Field(..., description="Skill to analyze")
    top_n: int = Field(
        default=10,
        ge=1,
        le=50,
        description="Number of top co-occurring skills"
    )
    
    class Config:
        json_schema_extra = {
            "example": {
                "skill": "Python",
                "top_n": 10
            }
        }


class AggregationRequest(BaseModel):
    """Request schema for field aggregation."""
    field: str = Field(
        ...,
        description="Field to aggregate (e.g., 'job_company_name', 'skills', 'location_country')"
    )
    size: int = Field(default=10, ge=1, le=100, description="Number of top values")
    filters: Optional[Dict[str, Any]] = Field(
        default=None,
        description="Optional filters to apply before aggregation"
    )
    
    class Config:
        json_schema_extra = {
            "example": {
                "field": "job_company_name",
                "size": 20,
                "filters": {
                    "title": "engineer"
                }
            }
        }


# ==================== Response Schemas ====================

class PersonSearchResult(BaseModel):
    """Single person search result."""
    pdl_id: str = Field(..., description="PDL unique identifier")
    score: float = Field(..., description="Search relevance score")
    full_name: Optional[str] = Field(None, description="Full name")
    job_title: Optional[str] = Field(None, description="Current job title")
    job_company_name: Optional[str] = Field(None, description="Current company")
    skills: Optional[List[str]] = Field(None, description="Skills")
    location_name: Optional[str] = Field(None, description="Location")
    inferred_years_experience: Optional[int] = Field(None, description="Years of experience")
    
    class Config:
        json_schema_extra = {
            "example": {
                "pdl_id": "abc123",
                "score": 2.34,
                "full_name": "John Doe",
                "job_title": "Senior Data Engineer",
                "job_company_name": "Netflix",
                "skills": ["Python", "Spark", "AWS"],
                "location_name": "San Francisco, CA",
                "inferred_years_experience": 8
            }
        }


class PersonSearchResponse(BaseModel):
    """Response schema for person search."""
    total: int = Field(..., description="Total number of matching results")
    hits: List[PersonSearchResult] = Field(..., description="Search results")
    took: Optional[int] = Field(None, description="Query execution time (ms)")
    max_score: Optional[float] = Field(None, description="Highest relevance score")
    fallback: bool = Field(default=False, description="Whether PostgreSQL fallback was used")
    
    class Config:
        json_schema_extra = {
            "example": {
                "total": 142,
                "hits": [],
                "took": 23,
                "max_score": 3.45,
                "fallback": False
            }
        }


class SkillSearchResult(PersonSearchResult):
    """Skill search result with match information."""
    matched_skills: List[str] = Field(..., description="Skills that matched the query")
    match_count: int = Field(..., description="Number of matched skills")


class SkillSearchResponse(BaseModel):
    """Response schema for skill search."""
    total: int = Field(..., description="Total number of results")
    hits: List[SkillSearchResult] = Field(..., description="Matching persons")


class CareerTransitionResult(BaseModel):
    """Single career transition result."""
    pdl_id: str = Field(..., description="Person ID")
    name: Optional[str] = Field(None, description="Person name")
    current_title: Optional[str] = Field(None, description="Current title")
    previous_title: Optional[str] = Field(None, description="Title at previous company")
    transition_date: Optional[str] = Field(None, description="When they left previous company")
    current_start_date: Optional[str] = Field(None, description="When they started current company")


class CareerTransitionResponse(BaseModel):
    """Response schema for career transitions."""
    from_company: str = Field(..., description="Starting company")
    to_company: str = Field(..., description="Destination company")
    transitions: List[CareerTransitionResult] = Field(..., description="People who made this transition")
    total: int = Field(..., description="Number of transitions found")


class ConnectedCompany(BaseModel):
    """Connected company in network."""
    company_name: str = Field(..., description="Company name")
    industry: Optional[str] = Field(None, description="Industry")
    shared_people: int = Field(..., description="Number of shared employees")


class CompanyNetworkResponse(BaseModel):
    """Response schema for company network."""
    source_company: str = Field(..., description="Source company")
    connected_companies: List[ConnectedCompany] = Field(..., description="Connected companies")
    total: int = Field(..., description="Number of connected companies")


class SkillCooccurrence(BaseModel):
    """Skill co-occurrence data."""
    cooccurring_skill: str = Field(..., description="Skill name")
    count: int = Field(..., description="Number of people with both skills")


class SkillCooccurrenceResponse(BaseModel):
    """Response schema for skill co-occurrence."""
    skill: str = Field(..., description="Original skill")
    cooccurring_skills: List[SkillCooccurrence] = Field(..., description="Co-occurring skills")
    total: int = Field(..., description="Number of co-occurring skills found")


class AggregationBucket(BaseModel):
    """Single aggregation bucket."""
    key: str = Field(..., description="Bucket key (field value)")
    count: int = Field(..., description="Number of documents")


class AggregationResponse(BaseModel):
    """Response schema for aggregations."""
    field: str = Field(..., description="Aggregated field")
    total_docs: int = Field(..., description="Total documents considered")
    buckets: List[AggregationBucket] = Field(..., description="Aggregation buckets")
    
    class Config:
        json_schema_extra = {
            "example": {
                "field": "job_company_name",
                "total_docs": 1234,
                "buckets": [
                    {"key": "Netflix", "count": 156},
                    {"key": "Google", "count": 143},
                    {"key": "Amazon", "count": 128}
                ]
            }
        }

