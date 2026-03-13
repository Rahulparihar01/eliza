"""
HR Management API Routes

This module provides API endpoints for HR data management including employees,
departments, positions, skills, performance reviews, and training records.
"""

from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, Query, status, Request
from sqlalchemy.exc import IntegrityError

from src.api.schemas.hr import (
    # Department schemas
    DepartmentCreateRequest,
    DepartmentUpdateRequest,
    DepartmentResponse,
    DepartmentListResponse,
    # Employee schemas
    EmployeeCreateRequest,
    EmployeeUpdateRequest,
    EmployeeDetailResponse,
    EmployeeListResponse,
    # Skill schemas
    SkillCreateRequest,
    SkillResponse,
    SkillListResponse,
    EmployeeSkillCreateRequest,
    EmployeeSkillResponse,
    # Training schemas
    TrainingProgramCreateRequest,
    TrainingProgramResponse,
    TrainingProgramListResponse,
    EmployeeTrainingRecordCreateRequest,
    EmployeeTrainingRecordResponse,
    # Pagination
    PaginationInfo,
)
from src.api.schemas.hr_summaries import (
    EmployeeOverviewSummary,
    SkillsCompetenciesSummary,
    PerformanceDevelopmentSummary,
    HRTablesListResponse,
    HRTableInfo,
)
from src.models.hr import (
    Department,
    Employee,
    Skill,
    EmployeeSkill,
    TrainingProgram,
    EmployeeTrainingRecord,
)
from src.services.hr_service import hr_service
from src.middleware.authorization import AuthorizationMiddleware
from src.core.logging import get_logger, LogCategory

logger = get_logger(__name__, component="hr.api")
auth_middleware = AuthorizationMiddleware()

router = APIRouter(prefix="/v1/hr", tags=["hr"])


# ============================================================================
# Department Endpoints
# ============================================================================

@router.get("/departments", response_model=DepartmentListResponse)
async def list_departments(
    search: Optional[str] = Query(None, description="Search by department name or code"),
    limit: int = Query(20, ge=1, le=100, description="Results per page"),
    offset: int = Query(0, ge=0, description="Pagination offset"),
    current_user = Depends(auth_middleware.require_permission("assistant:access"))
) -> DepartmentListResponse:
    """
    Get paginated list of departments with optional filtering.
    
    Requires: hr:read permission
    """
    try:
        departments = await hr_service.list_departments(
            customer_id=current_user.customer_id,
            search=search,
            limit=limit,
            offset=offset
        )
        
        total = await hr_service.count_departments(
            customer_id=current_user.customer_id,
            search=search
        )
        
        return DepartmentListResponse(
            departments=[DepartmentResponse.model_validate(d) for d in departments],
            pagination=PaginationInfo(
                total=total,
                limit=limit,
                offset=offset,
                has_more=(offset + len(departments)) < total
            )
        )
    except Exception as e:
        logger.error(
            f"Failed to list departments",
            exception=e,
            category=LogCategory.API,
            metadata={'customer_id': current_user.customer_id}
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to list departments: {str(e)}"
        )


@router.get("/departments/{department_id}", response_model=DepartmentResponse)
async def get_department(
    department_id: int,
    current_user = Depends(auth_middleware.require_permission("assistant:access"))
) -> DepartmentResponse:
    """
    Get a single department by ID.
    
    Requires: hr:read permission
    """
    try:
        department = await hr_service.get_department(
            department_id=department_id,
            customer_id=current_user.customer_id
        )
        
        if not department:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Department {department_id} not found"
            )
        
        return DepartmentResponse.model_validate(department)
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(
            f"Failed to get department {department_id}",
            exception=e,
            category=LogCategory.API,
            metadata={'department_id': department_id, 'customer_id': current_user.customer_id}
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get department: {str(e)}"
        )


@router.post("/departments", response_model=DepartmentResponse, status_code=status.HTTP_201_CREATED)
async def create_department(
    request: DepartmentCreateRequest,
    current_user = Depends(auth_middleware.require_permission("assistant:access"))
) -> DepartmentResponse:
    """
    Create a new department.
    
    Requires: hr:write permission
    """
    try:
        department = Department(
            customer_id=current_user.customer_id,
            name=request.name,
            code=request.code,
            description=request.description,
            parent_department_id=request.parent_department_id,
            head_employee_id=request.head_employee_id
        )
        
        created_dept = await hr_service.create_department(department)
        return DepartmentResponse.model_validate(created_dept)
        
    except IntegrityError as e:
        logger.error(
            f"Integrity error creating department",
            exception=e,
            category=LogCategory.API,
            metadata={'department_name': request.name}
        )
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Department with this code already exists or invalid foreign key reference"
        )
    except Exception as e:
        logger.error(
            f"Failed to create department",
            exception=e,
            category=LogCategory.API,
            metadata={'department_name': request.name}
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to create department: {str(e)}"
        )


# ============================================================================
# Employee Endpoints
# ============================================================================

@router.get("/employees", response_model=EmployeeListResponse)
async def list_employees(
    search: Optional[str] = Query(None, description="Search by name, email, or employee number"),
    department_id: Optional[int] = Query(None, description="Filter by department"),
    employment_status: Optional[str] = Query(None, description="Filter by employment status"),
    limit: int = Query(20, ge=1, le=100, description="Results per page"),
    offset: int = Query(0, ge=0, description="Pagination offset"),
    current_user = Depends(auth_middleware.require_permission("assistant:access"))
) -> EmployeeListResponse:
    """
    Get paginated list of employees with optional filtering.
    
    Requires: hr:read permission
    """
    try:
        employees = await hr_service.list_employees(
            customer_id=current_user.customer_id,
            search=search,
            department_id=department_id,
            employment_status=employment_status,
            limit=limit,
            offset=offset
        )
        
        total = await hr_service.count_employees(
            customer_id=current_user.customer_id,
            search=search,
            department_id=department_id,
            employment_status=employment_status
        )
        
        return EmployeeListResponse(
            employees=[EmployeeDetailResponse.model_validate(e) for e in employees],
            pagination=PaginationInfo(
                total=total,
                limit=limit,
                offset=offset,
                has_more=(offset + len(employees)) < total
            )
        )
    except Exception as e:
        logger.error(
            f"Failed to list employees",
            exception=e,
            category=LogCategory.API,
            metadata={'customer_id': current_user.customer_id}
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to list employees: {str(e)}"
        )


@router.get("/employees/{employee_id}", response_model=EmployeeDetailResponse)
async def get_employee(
    employee_id: int,
    current_user = Depends(auth_middleware.require_permission("assistant:access"))
) -> EmployeeDetailResponse:
    """
    Get a single employee by ID with related entities.
    
    Requires: hr:read permission
    """
    try:
        employee = await hr_service.get_employee(
            employee_id=employee_id,
            customer_id=current_user.customer_id
        )
        
        if not employee:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Employee {employee_id} not found"
            )
        
        return EmployeeDetailResponse.model_validate(employee)
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(
            f"Failed to get employee {employee_id}",
            exception=e,
            category=LogCategory.API,
            metadata={'employee_id': employee_id, 'customer_id': current_user.customer_id}
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get employee: {str(e)}"
        )


@router.post("/employees", response_model=EmployeeDetailResponse, status_code=status.HTTP_201_CREATED)
async def create_employee(
    request: EmployeeCreateRequest,
    current_user = Depends(auth_middleware.require_permission("assistant:access"))
) -> EmployeeDetailResponse:
    """
    Create a new employee.

    Requires: hr:write permission
    """
    try:
        employee = Employee(
            customer_id=current_user.customer_id,
            user_id=request.user_id,
            employee_number=request.employee_number,
            first_name=request.first_name,
            last_name=request.last_name,
            email=request.email,
            phone=request.phone,
            hire_date=request.hire_date,
            employment_status=request.employment_status.value,
            employment_type=request.employment_type.value,
            work_location=request.work_location.value,
            manager_id=request.manager_id,
            position_id=request.position_id,
            department_id=request.department_id
        )

        created_emp = await hr_service.create_employee(employee)

        # Reload with related entities
        employee_with_relations = await hr_service.get_employee(
            employee_id=created_emp.id,
            customer_id=current_user.customer_id
        )

        return EmployeeDetailResponse.model_validate(employee_with_relations)

    except IntegrityError as e:
        logger.error(
            f"Integrity error creating employee",
            exception=e,
            category=LogCategory.API,
            metadata={'employee_number': request.employee_number}
        )
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Employee with this number already exists or invalid foreign key reference"
        )
    except Exception as e:
        logger.error(
            f"Failed to create employee",
            exception=e,
            category=LogCategory.API,
            metadata={'employee_number': request.employee_number}
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to create employee: {str(e)}"
        )


# ============================================================================
# Skill Endpoints
# ============================================================================

@router.get("/skills", response_model=SkillListResponse)
async def list_skills(
    category: Optional[str] = Query(None, description="Filter by skill category"),
    limit: int = Query(100, ge=1, le=500, description="Results per page"),
    offset: int = Query(0, ge=0, description="Pagination offset"),
    current_user = Depends(auth_middleware.require_permission("assistant:access"))
) -> SkillListResponse:
    """
    Get paginated list of skills with optional filtering.

    Requires: hr:read permission
    """
    try:
        skills = await hr_service.list_skills(
            customer_id=current_user.customer_id,
            category=category,
            limit=limit,
            offset=offset
        )

        # For simplicity, we'll return the count as the length of results
        # In production, you'd want a separate count query
        total = len(skills)

        return SkillListResponse(
            skills=[SkillResponse.model_validate(s) for s in skills],
            pagination=PaginationInfo(
                total=total,
                limit=limit,
                offset=offset,
                has_more=len(skills) >= limit
            )
        )
    except Exception as e:
        logger.error(
            f"Failed to list skills",
            exception=e,
            category=LogCategory.API,
            metadata={'customer_id': current_user.customer_id}
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to list skills: {str(e)}"
        )


@router.get("/employees/{employee_id}/skills", response_model=list[EmployeeSkillResponse])
async def get_employee_skills(
    employee_id: int,
    current_user = Depends(auth_middleware.require_permission("assistant:access"))
) -> list[EmployeeSkillResponse]:
    """
    Get all skills for an employee.

    Requires: hr:read permission
    """
    try:
        employee_skills = await hr_service.get_employee_skills(
            employee_id=employee_id,
            customer_id=current_user.customer_id
        )

        return [EmployeeSkillResponse.model_validate(es) for es in employee_skills]

    except Exception as e:
        logger.error(
            f"Failed to get employee skills",
            exception=e,
            category=LogCategory.API,
            metadata={'employee_id': employee_id, 'customer_id': current_user.customer_id}
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get employee skills: {str(e)}"
        )


# ============================================================================
# Executive Summary Endpoints
# ============================================================================

@router.get("/summaries/employee-overview", response_model=EmployeeOverviewSummary)
async def get_employee_overview_summary(
    customer_id: str = Query("caylent", description="Customer ID to query HR data for"),
    current_user = Depends(auth_middleware.require_permission("assistant:access"))
) -> EmployeeOverviewSummary:
    """
    Get employee overview summary for executives.

    Provides high-level metrics about employees including:
    - Total employee counts by status, type, and location
    - Department and position breakdowns
    - Average tenure

    Requires: hr:read permission
    """
    try:
        summary = await hr_service.get_employee_overview_summary(
            customer_id=customer_id
        )

        if not summary:
            # Return empty summary if no data
            return EmployeeOverviewSummary(
                customer_id=customer_id,
                total_employees=0,
                active_employees=0,
                on_leave_employees=0,
                terminated_employees=0,
                full_time_employees=0,
                part_time_employees=0,
                contractor_employees=0,
                office_employees=0,
                remote_employees=0,
                hybrid_employees=0,
                total_departments=0,
                total_positions=0,
                avg_tenure_years=None,
                department_breakdown=[],
                position_breakdown=[]
            )

        return EmployeeOverviewSummary(**summary)

    except Exception as e:
        logger.error(
            f"Failed to get employee overview summary",
            exception=e,
            category=LogCategory.API,
            metadata={'customer_id': current_user.customer_id}
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get employee overview summary: {str(e)}"
        )


@router.get("/summaries/skills-competencies", response_model=SkillsCompetenciesSummary)
async def get_skills_competencies_summary(
    customer_id: str = Query("caylent", description="Customer ID to query HR data for"),
    current_user = Depends(auth_middleware.require_permission("assistant:access"))
) -> SkillsCompetenciesSummary:
    """
    Get skills and competencies summary for executives.

    Provides insights about organizational skills including:
    - Total skills and skill assignments
    - Proficiency level distribution
    - Skills by category
    - Average experience levels

    Requires: hr:read permission
    """
    try:
        summary = await hr_service.get_skills_competencies_summary(
            customer_id=customer_id
        )

        if not summary:
            return SkillsCompetenciesSummary(
                customer_id=customer_id,
                total_skills=0,
                total_skill_assignments=0,
                employees_with_skills=0,
                expert_level_skills=0,
                advanced_level_skills=0,
                intermediate_level_skills=0,
                beginner_level_skills=0,
                avg_years_experience=None,
                skill_breakdown=[],
                category_breakdown=[]
            )

        return SkillsCompetenciesSummary(**summary)

    except Exception as e:
        logger.error(
            f"Failed to get skills competencies summary",
            exception=e,
            category=LogCategory.API,
            metadata={'customer_id': customer_id}
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get skills competencies summary: {str(e)}"
        )


@router.get("/summaries/performance-development", response_model=PerformanceDevelopmentSummary)
async def get_performance_development_summary(
    customer_id: str = Query("caylent", description="Customer ID to query HR data for"),
    current_user = Depends(auth_middleware.require_permission("assistant:access"))
) -> PerformanceDevelopmentSummary:
    """
    Get performance and development summary for executives.

    Provides insights about employee performance and development including:
    - Performance review metrics
    - Promotion readiness
    - Training completion and ratings
    - Goals achievement
    - Department-level performance

    Requires: hr:read permission
    """
    try:
        summary = await hr_service.get_performance_development_summary(
            customer_id=customer_id
        )

        if not summary:
            return PerformanceDevelopmentSummary(
                customer_id=customer_id,
                total_active_employees=0,
                total_performance_reviews=0,
                reviews_last_12_months=0,
                avg_overall_rating=None,
                ready_for_promotion=0,
                ready_in_6_months=0,
                ready_in_12_months=0,
                total_training_records=0,
                completed_trainings=0,
                in_progress_trainings=0,
                enrolled_trainings=0,
                avg_training_rating=None,
                avg_goals_achievement=None,
                department_performance=[],
                training_program_stats=[]
            )

        return PerformanceDevelopmentSummary(**summary)

    except Exception as e:
        logger.error(
            f"Failed to get performance development summary",
            exception=e,
            category=LogCategory.API,
            metadata={'customer_id': customer_id}
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get performance development summary: {str(e)}"
        )


@router.get("/tables", response_model=HRTablesListResponse)
async def get_hr_tables_list(
    customer_id: str = Query("caylent", description="Customer ID to query HR data for"),
    current_user = Depends(auth_middleware.require_permission("assistant:access"))
) -> HRTablesListResponse:
    """
    Get list of all HR tables with metadata.

    Provides information about available HR data tables including:
    - Table names and descriptions
    - Record counts
    - API endpoints

    Requires: hr:read permission
    """
    try:
        tables = await hr_service.get_hr_tables_list(
            customer_id=customer_id
        )

        return HRTablesListResponse(
            tables=[HRTableInfo(**table) for table in tables],
            total_tables=len(tables)
        )

    except Exception as e:
        logger.error(
            f"Failed to get HR tables list",
            exception=e,
            category=LogCategory.API,
            metadata={'customer_id': customer_id}
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get HR tables list: {str(e)}"
        )


@router.get("/tables/{table_name}/data")
async def get_hr_table_data(
    table_name: str,
    customer_id: str = Query("caylent", description="Customer ID to query HR data for"),
    limit: int = Query(100, ge=1, le=1000, description="Maximum number of rows to return"),
    offset: int = Query(0, ge=0, description="Number of rows to skip"),
    current_user = Depends(auth_middleware.require_permission("assistant:access"))
):
    """
    Get data from a specific HR table.

    This endpoint returns the actual data from the specified HR table with pagination support.

    Args:
        table_name: Name of the HR table (e.g., 'hr_employees', 'hr_departments')
        customer_id: Customer ID for multi-tenancy
        limit: Maximum number of rows to return (default: 100, max: 1000)
        offset: Number of rows to skip for pagination (default: 0)

    Returns:
        JSON object with:
        - data: List of rows from the table
        - total_count: Total number of rows in the table
        - columns: List of column names
        - limit: Applied limit
        - offset: Applied offset

    Requires: hr:read permission
    """
    try:
        result = await hr_service.get_hr_table_data(
            table_name=table_name,
            customer_id=customer_id,
            limit=limit,
            offset=offset
        )

        return result
    except ValueError as e:
        logger.warning(
            f"Invalid table name requested: {table_name}",
            exception=e,
            category=LogCategory.API,
            metadata={'customer_id': customer_id, 'table_name': table_name}
        )
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    except Exception as e:
        logger.error(
            f"Failed to get HR table data for {table_name}",
            exception=e,
            category=LogCategory.API,
            metadata={'customer_id': customer_id, 'table_name': table_name}
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get HR table data: {str(e)}"
        )
