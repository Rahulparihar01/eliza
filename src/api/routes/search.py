"""
API routes for person search.

Provides endpoints for searching and analyzing person data across
Elasticsearch, Neo4j, and PostgreSQL.
"""
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from src.models.database import get_db
from src.middleware.authorization import get_current_user
from src.api.schemas.search_schemas import (
    PersonSearchRequest,
    PersonSearchResponse,
    SkillSearchRequest,
    SkillSearchResponse,
    CareerTransitionRequest,
    CareerTransitionResponse,
    CompanyNetworkRequest,
    CompanyNetworkResponse,
    SkillCooccurrenceRequest,
    SkillCooccurrenceResponse,
    AggregationRequest,
    AggregationResponse,
    PersonSearchResult,
    SkillSearchResult,
    CareerTransitionResult,
    ConnectedCompany,
    SkillCooccurrence,
    AggregationBucket,
)
from src.models.auth import User
from src.services.search.person_search_service import PersonSearchService
from src.core.logging import get_logger, LogCategory

logger = get_logger(__name__, LogCategory.API)

router = APIRouter(
    prefix="/search",
    tags=["search"],
    responses={404: {"description": "Not found"}}
)


def get_search_service(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
) -> PersonSearchService:
    """Dependency to get PersonSearchService instance."""
    return PersonSearchService(db, current_user.customer_id)


@router.post(
    "/persons",
    response_model=PersonSearchResponse,
    summary="Search for persons",
    description="Full-text search across person data with optional filters"
)
async def search_persons(
    request: PersonSearchRequest,
    search_service: PersonSearchService = Depends(get_search_service),
    current_user: User = Depends(get_current_user)
):
    """
    Search for persons using full-text search.
    
    Searches across:
    - Name (highest weight)
    - Job title
    - Skills
    - Company name
    - Location
    
    Supports fuzzy matching and filters.
    """
    try:
        logger.info(
            "person_search_request",
            user_id=current_user.id,
            customer_id=current_user.customer_id,
            query=request.query
        )
        
        result = search_service.search_persons(
            query=request.query,
            filters=request.filters,
            size=request.size,
            from_=request.from_
        )
        
        # Transform to response model
        hits = [PersonSearchResult(**hit) for hit in result['hits']]
        
        return PersonSearchResponse(
            total=result['total'],
            hits=hits,
            took=result.get('took'),
            max_score=result.get('max_score'),
            fallback=result.get('fallback', False)
        )
        
    except Exception as e:
        logger.error(
            "person_search_failed",
            user_id=current_user.id,
            error=str(e),
            exc_info=True
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Search failed: {str(e)}"
        )
    finally:
        search_service.close()


@router.post(
    "/persons/by-skills",
    response_model=SkillSearchResponse,
    summary="Search by skills",
    description="Find persons with specific skill combinations"
)
async def search_by_skills(
    request: SkillSearchRequest,
    search_service: PersonSearchService = Depends(get_search_service),
    current_user: User = Depends(get_current_user)
):
    """
    Find persons with specific skill combinations.
    
    Returns persons ranked by how many of the requested skills they have.
    """
    try:
        logger.info(
            "skill_search_request",
            user_id=current_user.id,
            skills=request.skills,
            min_match=request.min_match
        )
        
        result = search_service.search_by_skills(
            skills=request.skills,
            min_match=request.min_match,
            size=request.size
        )
        
        # Transform to response model
        hits = [SkillSearchResult(**hit) for hit in result['hits']]
        
        return SkillSearchResponse(
            total=result['total'],
            hits=hits
        )
        
    except Exception as e:
        logger.error(
            "skill_search_failed",
            user_id=current_user.id,
            error=str(e),
            exc_info=True
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Skill search failed: {str(e)}"
        )
    finally:
        search_service.close()


@router.post(
    "/persons/career-transitions",
    response_model=CareerTransitionResponse,
    summary="Find career transitions",
    description="Find people who moved from one company to another"
)
async def find_career_transitions(
    request: CareerTransitionRequest,
    search_service: PersonSearchService = Depends(get_search_service),
    current_user: User = Depends(get_current_user)
):
    """
    Find people who transitioned from one company to another.
    
    Uses Neo4j graph queries to find career path patterns.
    """
    try:
        logger.info(
            "career_transition_request",
            user_id=current_user.id,
            from_company=request.from_company,
            to_company=request.to_company
        )
        
        transitions = search_service.find_career_transitions(
            from_company=request.from_company,
            to_company=request.to_company,
            limit=request.limit
        )
        
        # Transform to response model
        results = [CareerTransitionResult(**t) for t in transitions]
        
        return CareerTransitionResponse(
            from_company=request.from_company,
            to_company=request.to_company,
            transitions=results,
            total=len(results)
        )
        
    except Exception as e:
        logger.error(
            "career_transition_query_failed",
            user_id=current_user.id,
            error=str(e),
            exc_info=True
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Career transition query failed: {str(e)}"
        )
    finally:
        search_service.close()


@router.post(
    "/companies/network",
    response_model=CompanyNetworkResponse,
    summary="Get company network",
    description="Find companies connected through shared employees"
)
async def get_company_network(
    request: CompanyNetworkRequest,
    search_service: PersonSearchService = Depends(get_search_service),
    current_user: User = Depends(get_current_user)
):
    """
    Get network of companies connected through people.
    
    Finds companies that share employees with the target company,
    ranked by number of shared connections.
    """
    try:
        logger.info(
            "company_network_request",
            user_id=current_user.id,
            company=request.company_name
        )
        
        result = search_service.get_company_network(
            company_name=request.company_name,
            max_hops=request.max_hops,
            limit=request.limit
        )
        
        # Transform to response model
        companies = [ConnectedCompany(**c) for c in result['connected_companies']]
        
        return CompanyNetworkResponse(
            source_company=result['source_company'],
            connected_companies=companies,
            total=result['total']
        )
        
    except Exception as e:
        logger.error(
            "company_network_query_failed",
            user_id=current_user.id,
            error=str(e),
            exc_info=True
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Company network query failed: {str(e)}"
        )
    finally:
        search_service.close()


@router.post(
    "/skills/cooccurrence",
    response_model=SkillCooccurrenceResponse,
    summary="Analyze skill co-occurrence",
    description="Find skills that commonly occur together"
)
async def analyze_skill_cooccurrence(
    request: SkillCooccurrenceRequest,
    search_service: PersonSearchService = Depends(get_search_service),
    current_user: User = Depends(get_current_user)
):
    """
    Find skills that commonly occur with a given skill.
    
    Useful for understanding skill stacks and relationships.
    """
    try:
        logger.info(
            "skill_cooccurrence_request",
            user_id=current_user.id,
            skill=request.skill
        )
        
        cooccurring = search_service.get_skill_cooccurrence(
            skill=request.skill,
            top_n=request.top_n
        )
        
        # Transform to response model
        skills = [SkillCooccurrence(**s) for s in cooccurring]
        
        return SkillCooccurrenceResponse(
            skill=request.skill,
            cooccurring_skills=skills,
            total=len(skills)
        )
        
    except Exception as e:
        logger.error(
            "skill_cooccurrence_failed",
            user_id=current_user.id,
            error=str(e),
            exc_info=True
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Skill co-occurrence analysis failed: {str(e)}"
        )
    finally:
        search_service.close()


@router.post(
    "/aggregate",
    response_model=AggregationResponse,
    summary="Aggregate by field",
    description="Get aggregation counts for any field"
)
async def aggregate_field(
    request: AggregationRequest,
    search_service: PersonSearchService = Depends(get_search_service),
    current_user: User = Depends(get_current_user)
):
    """
    Get aggregation counts for a field.
    
    Useful for faceted search, analytics, and understanding data distribution.
    
    Examples:
    - Top companies: field='job_company_name'
    - Top skills: field='skills'
    - Top locations: field='location_country'
    """
    try:
        logger.info(
            "aggregation_request",
            user_id=current_user.id,
            field=request.field
        )
        
        result = search_service.aggregate_by_field(
            field=request.field,
            size=request.size,
            filters=request.filters
        )
        
        # Transform to response model
        buckets = [AggregationBucket(**b) for b in result['buckets']]
        
        return AggregationResponse(
            field=result['field'],
            total_docs=result['total_docs'],
            buckets=buckets
        )
        
    except Exception as e:
        logger.error(
            "aggregation_failed",
            user_id=current_user.id,
            error=str(e),
            exc_info=True
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Aggregation failed: {str(e)}"
        )
    finally:
        search_service.close()


@router.get(
    "/persons/{pdl_id}",
    response_model=PersonSearchResult,
    summary="Get person by ID",
    description="Retrieve a single person by their PDL ID"
)
async def get_person_by_id(
    pdl_id: str,
    search_service: PersonSearchService = Depends(get_search_service),
    current_user: User = Depends(get_current_user)
):
    """Get a single person by their PDL ID."""
    try:
        # Search for exact PDL ID
        result = search_service.search_persons(
            query=pdl_id,
            filters={'pdl_id': pdl_id},
            size=1
        )
        
        if not result['hits']:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Person not found: {pdl_id}"
            )
        
        return PersonSearchResult(**result['hits'][0])
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(
            "get_person_failed",
            user_id=current_user.id,
            pdl_id=pdl_id,
            error=str(e),
            exc_info=True
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to retrieve person: {str(e)}"
        )
    finally:
        search_service.close()

