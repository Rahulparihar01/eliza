"""
Pydantic schemas for HR data management.

This module contains request/response schemas for all HR entities following
the Feature Development Guide patterns with comprehensive Field descriptions,
examples, and validation.
"""

from datetime import date, datetime
from typing import Optional, List, Dict, Any
from enum import Enum
from pydantic import BaseModel, Field, validator, EmailStr
from decimal import Decimal


# ============================================================================
# Enums
# ============================================================================

class EmploymentStatus(str, Enum):
    """Employment status enum"""
    ACTIVE = "active"
    ON_LEAVE = "on_leave"
    TERMINATED = "terminated"
    RETIRED = "retired"


class EmploymentType(str, Enum):
    """Employment type enum"""
    FULL_TIME = "full_time"
    PART_TIME = "part_time"
    CONTRACTOR = "contractor"
    INTERN = "intern"


class WorkLocation(str, Enum):
    """Work location enum"""
    OFFICE = "office"
    REMOTE = "remote"
    HYBRID = "hybrid"


class ChangeType(str, Enum):
    """Employment change type enum"""
    HIRE = "hire"
    PROMOTION = "promotion"
    TRANSFER = "transfer"
    DEMOTION = "demotion"
    TERMINATION = "termination"
    ROLE_CHANGE = "role_change"


class ProficiencyLevel(str, Enum):
    """Skill proficiency level enum"""
    BEGINNER = "beginner"
    INTERMEDIATE = "intermediate"
    ADVANCED = "advanced"
    EXPERT = "expert"


class TrainingStatus(str, Enum):
    """Training status enum"""
    ENROLLED = "enrolled"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class ReviewStatus(str, Enum):
    """Performance review status enum"""
    DRAFT = "draft"
    PENDING_EMPLOYEE_REVIEW = "pending_employee_review"
    PENDING_MANAGER_APPROVAL = "pending_manager_approval"
    COMPLETED = "completed"
    ARCHIVED = "archived"


class TimeOffStatus(str, Enum):
    """Time off request status enum"""
    PENDING = "pending"
    APPROVED = "approved"
    DENIED = "denied"
    CANCELLED = "cancelled"


# ============================================================================
# Department Schemas
# ============================================================================

class DepartmentBase(BaseModel):
    """Base department schema"""
    name: str = Field(..., min_length=1, max_length=255, description="Department name")
    code: str = Field(..., min_length=1, max_length=50, description="Department code")
    description: Optional[str] = Field(None, description="Department description")
    parent_department_id: Optional[int] = Field(None, description="Parent department ID for hierarchical structure")
    head_employee_id: Optional[int] = Field(None, description="Department head employee ID")


class DepartmentCreateRequest(DepartmentBase):
    """Request schema for creating a department"""
    
    class Config:
        json_schema_extra = {
            "example": {
                "name": "Engineering",
                "code": "ENG",
                "description": "Cloud engineering and architecture team",
                "parent_department_id": None,
                "head_employee_id": None
            }
        }


class DepartmentUpdateRequest(BaseModel):
    """Request schema for updating a department"""
    name: Optional[str] = Field(None, min_length=1, max_length=255, description="Department name")
    code: Optional[str] = Field(None, min_length=1, max_length=50, description="Department code")
    description: Optional[str] = Field(None, description="Department description")
    parent_department_id: Optional[int] = Field(None, description="Parent department ID")
    head_employee_id: Optional[int] = Field(None, description="Department head employee ID")


class DepartmentInfo(BaseModel):
    """Minimal department information for nested responses"""
    id: int
    name: str
    code: str
    
    class Config:
        from_attributes = True


class DepartmentResponse(DepartmentBase):
    """Response schema for department"""
    id: int
    customer_id: str
    created_at: datetime
    updated_at: Optional[datetime]
    
    class Config:
        from_attributes = True


# ============================================================================
# Position Schemas
# ============================================================================

class PositionBase(BaseModel):
    """Base position schema"""
    title: str = Field(..., min_length=1, max_length=255, description="Position title")
    level: str = Field(..., min_length=1, max_length=50, description="Position level (e.g., Junior, Mid, Senior, Staff, Principal)")
    job_family: str = Field(..., min_length=1, max_length=100, description="Job family (e.g., Engineering, Sales, Operations)")
    description: Optional[str] = Field(None, description="Position description")
    required_skills: Optional[Dict[str, Any]] = Field(None, description="Required skills as JSON")
    is_active: bool = Field(True, description="Whether position is active")


class PositionCreateRequest(PositionBase):
    """Request schema for creating a position"""
    
    class Config:
        json_schema_extra = {
            "example": {
                "title": "Senior Cloud Architect",
                "level": "Senior",
                "job_family": "Engineering",
                "description": "Lead cloud architecture and AWS solutions design",
                "required_skills": {
                    "aws_solutions_architect": "required",
                    "terraform": "required",
                    "kubernetes": "preferred"
                },
                "is_active": True
            }
        }


class PositionUpdateRequest(BaseModel):
    """Request schema for updating a position"""
    title: Optional[str] = Field(None, min_length=1, max_length=255, description="Position title")
    level: Optional[str] = Field(None, min_length=1, max_length=50, description="Position level")
    job_family: Optional[str] = Field(None, min_length=1, max_length=100, description="Job family")
    description: Optional[str] = Field(None, description="Position description")
    required_skills: Optional[Dict[str, Any]] = Field(None, description="Required skills as JSON")
    is_active: Optional[bool] = Field(None, description="Whether position is active")


class PositionInfo(BaseModel):
    """Minimal position information for nested responses"""
    id: int
    title: str
    level: str
    
    class Config:
        from_attributes = True


class PositionResponse(PositionBase):
    """Response schema for position"""
    id: int
    customer_id: str
    created_at: datetime
    updated_at: Optional[datetime]
    
    class Config:
        from_attributes = True


# ============================================================================
# Employee Schemas
# ============================================================================

class EmployeeBase(BaseModel):
    """Base employee schema"""
    employee_number: str = Field(..., min_length=1, max_length=50, description="Unique employee number")
    first_name: str = Field(..., min_length=1, max_length=100, description="Employee first name")
    last_name: str = Field(..., min_length=1, max_length=100, description="Employee last name")
    email: EmailStr = Field(..., description="Employee email address")
    phone: Optional[str] = Field(None, max_length=50, description="Employee phone number")
    hire_date: date = Field(..., description="Date of hire")
    employment_status: EmploymentStatus = Field(..., description="Employment status")
    employment_type: EmploymentType = Field(..., description="Employment type")
    work_location: WorkLocation = Field(..., description="Work location")
    manager_id: Optional[int] = Field(None, description="Manager employee ID")
    position_id: int = Field(..., description="Position ID")
    department_id: int = Field(..., description="Department ID")


class EmployeeCreateRequest(EmployeeBase):
    """Request schema for creating an employee"""
    user_id: Optional[int] = Field(None, description="Associated user ID if employee has platform access")
    
    class Config:
        json_schema_extra = {
            "example": {
                "employee_number": "EMP001",
                "first_name": "John",
                "last_name": "Doe",
                "email": "john.doe@caylent.com",
                "phone": "+1-555-0100",
                "hire_date": "2023-01-15",
                "employment_status": "active",
                "employment_type": "full_time",
                "work_location": "remote",
                "manager_id": None,
                "position_id": 1,
                "department_id": 1,
                "user_id": None
            }
        }


class EmployeeUpdateRequest(BaseModel):
    """Request schema for updating an employee"""
    first_name: Optional[str] = Field(None, min_length=1, max_length=100, description="Employee first name")
    last_name: Optional[str] = Field(None, min_length=1, max_length=100, description="Employee last name")
    email: Optional[EmailStr] = Field(None, description="Employee email address")
    phone: Optional[str] = Field(None, max_length=50, description="Employee phone number")
    employment_status: Optional[EmploymentStatus] = Field(None, description="Employment status")
    employment_type: Optional[EmploymentType] = Field(None, description="Employment type")
    work_location: Optional[WorkLocation] = Field(None, description="Work location")
    manager_id: Optional[int] = Field(None, description="Manager employee ID")
    position_id: Optional[int] = Field(None, description="Position ID")
    department_id: Optional[int] = Field(None, description="Department ID")


class EmployeeInfo(BaseModel):
    """Minimal employee information for nested responses"""
    id: int
    employee_number: str
    first_name: str
    last_name: str
    email: str

    class Config:
        from_attributes = True


class EmployeeResponse(EmployeeBase):
    """Response schema for employee"""
    id: int
    customer_id: str
    user_id: Optional[int]
    created_at: datetime
    updated_at: Optional[datetime]

    class Config:
        from_attributes = True


class EmployeeDetailResponse(EmployeeResponse):
    """Detailed employee response with related entities"""
    position: Optional[PositionInfo] = None
    department: Optional[DepartmentInfo] = None
    manager: Optional[EmployeeInfo] = None

    class Config:
        from_attributes = True


# ============================================================================
# Skill Schemas
# ============================================================================

class SkillBase(BaseModel):
    """Base skill schema"""
    name: str = Field(..., min_length=1, max_length=255, description="Skill name")
    category: str = Field(..., min_length=1, max_length=100, description="Skill category (e.g., AWS, DevOps, Programming)")
    description: Optional[str] = Field(None, description="Skill description")


class SkillCreateRequest(SkillBase):
    """Request schema for creating a skill"""

    class Config:
        json_schema_extra = {
            "example": {
                "name": "AWS Solutions Architect",
                "category": "Certification",
                "description": "AWS Certified Solutions Architect - Professional"
            }
        }


class SkillResponse(SkillBase):
    """Response schema for skill"""
    id: int
    customer_id: str
    created_at: datetime

    class Config:
        from_attributes = True


class EmployeeSkillBase(BaseModel):
    """Base employee skill schema"""
    skill_id: int = Field(..., description="Skill ID")
    proficiency_level: ProficiencyLevel = Field(..., description="Proficiency level")
    years_experience: Optional[float] = Field(None, ge=0, description="Years of experience with this skill")
    last_used_date: Optional[date] = Field(None, description="Date skill was last used")
    notes: Optional[str] = Field(None, description="Additional notes about the skill")


class EmployeeSkillCreateRequest(EmployeeSkillBase):
    """Request schema for adding a skill to an employee"""

    class Config:
        json_schema_extra = {
            "example": {
                "skill_id": 1,
                "proficiency_level": "expert",
                "years_experience": 5.5,
                "last_used_date": "2024-12-01",
                "notes": "Led multiple AWS migration projects"
            }
        }


class EmployeeSkillResponse(EmployeeSkillBase):
    """Response schema for employee skill"""
    id: int
    employee_id: int
    customer_id: str
    created_at: datetime
    updated_at: Optional[datetime]
    skill: Optional[SkillResponse] = None

    class Config:
        from_attributes = True


# ============================================================================
# Performance Review Schemas
# ============================================================================

class PerformanceReviewBase(BaseModel):
    """Base performance review schema"""
    review_period_start: date = Field(..., description="Review period start date")
    review_period_end: date = Field(..., description="Review period end date")
    review_type: str = Field(..., min_length=1, max_length=50, description="Review type (e.g., Annual, Mid-Year, Quarterly)")
    overall_rating: Optional[float] = Field(None, ge=1, le=5, description="Overall rating (1-5 scale)")
    goals_rating: Optional[float] = Field(None, ge=1, le=5, description="Goals achievement rating")
    competencies_rating: Optional[float] = Field(None, ge=1, le=5, description="Competencies rating")
    values_rating: Optional[float] = Field(None, ge=1, le=5, description="Company values rating")
    employee_comments: Optional[str] = Field(None, description="Employee self-assessment comments")
    manager_comments: Optional[str] = Field(None, description="Manager review comments")
    status: ReviewStatus = Field(..., description="Review status")


class PerformanceReviewCreateRequest(PerformanceReviewBase):
    """Request schema for creating a performance review"""
    employee_id: int = Field(..., description="Employee ID being reviewed")
    reviewer_employee_id: int = Field(..., description="Reviewer (manager) employee ID")

    class Config:
        json_schema_extra = {
            "example": {
                "employee_id": 1,
                "reviewer_employee_id": 2,
                "review_period_start": "2024-01-01",
                "review_period_end": "2024-12-31",
                "review_type": "Annual",
                "overall_rating": 4.5,
                "goals_rating": 4.0,
                "competencies_rating": 5.0,
                "values_rating": 4.5,
                "employee_comments": "Exceeded expectations on cloud migration projects",
                "manager_comments": "Outstanding performance, demonstrated leadership",
                "status": "completed"
            }
        }


class PerformanceReviewResponse(PerformanceReviewBase):
    """Response schema for performance review"""
    id: int
    employee_id: int
    reviewer_employee_id: int
    customer_id: str
    employee_acknowledged_at: Optional[datetime]
    created_at: datetime
    updated_at: Optional[datetime]

    class Config:
        from_attributes = True


# ============================================================================
# Training Schemas
# ============================================================================

class TrainingProgramBase(BaseModel):
    """Base training program schema"""
    name: str = Field(..., min_length=1, max_length=255, description="Training program name")
    description: Optional[str] = Field(None, description="Training program description")
    provider: Optional[str] = Field(None, max_length=255, description="Training provider")
    duration_hours: Optional[float] = Field(None, ge=0, description="Duration in hours")
    cost: Optional[Decimal] = Field(None, ge=0, description="Cost of training")
    is_mandatory: bool = Field(False, description="Whether training is mandatory")


class TrainingProgramCreateRequest(TrainingProgramBase):
    """Request schema for creating a training program"""

    class Config:
        json_schema_extra = {
            "example": {
                "name": "AWS Solutions Architect Certification Prep",
                "description": "Preparation course for AWS SAA-C03 exam",
                "provider": "A Cloud Guru",
                "duration_hours": 40.0,
                "cost": 299.00,
                "is_mandatory": False
            }
        }


class TrainingProgramResponse(TrainingProgramBase):
    """Response schema for training program"""
    id: int
    customer_id: str
    created_at: datetime
    updated_at: Optional[datetime]

    class Config:
        from_attributes = True


class EmployeeTrainingRecordBase(BaseModel):
    """Base employee training record schema"""
    training_program_id: int = Field(..., description="Training program ID")
    enrollment_date: date = Field(..., description="Enrollment date")
    start_date: Optional[date] = Field(None, description="Training start date")
    completion_date: Optional[date] = Field(None, description="Training completion date")
    status: TrainingStatus = Field(..., description="Training status")
    score: Optional[float] = Field(None, ge=0, le=100, description="Score/grade (0-100)")
    notes: Optional[str] = Field(None, description="Additional notes")


class EmployeeTrainingRecordCreateRequest(EmployeeTrainingRecordBase):
    """Request schema for enrolling employee in training"""

    class Config:
        json_schema_extra = {
            "example": {
                "training_program_id": 1,
                "enrollment_date": "2024-01-15",
                "start_date": "2024-02-01",
                "completion_date": None,
                "status": "in_progress",
                "score": None,
                "notes": "Enrolled for Q1 2024"
            }
        }


class EmployeeTrainingRecordResponse(EmployeeTrainingRecordBase):
    """Response schema for employee training record"""
    id: int
    employee_id: int
    customer_id: str
    created_at: datetime
    updated_at: Optional[datetime]
    training_program: Optional[TrainingProgramResponse] = None

    class Config:
        from_attributes = True


# ============================================================================
# Pagination and List Responses
# ============================================================================

class PaginationInfo(BaseModel):
    """Pagination information"""
    total: int = Field(..., description="Total number of items")
    limit: int = Field(..., description="Items per page")
    offset: int = Field(..., description="Current offset")
    has_more: bool = Field(..., description="Whether there are more items")


class EmployeeListResponse(BaseModel):
    """Response schema for employee list"""
    employees: List[EmployeeDetailResponse]
    pagination: PaginationInfo


class DepartmentListResponse(BaseModel):
    """Response schema for department list"""
    departments: List[DepartmentResponse]
    pagination: PaginationInfo


class SkillListResponse(BaseModel):
    """Response schema for skill list"""
    skills: List[SkillResponse]
    pagination: PaginationInfo


class TrainingProgramListResponse(BaseModel):
    """Response schema for training program list"""
    training_programs: List[TrainingProgramResponse]
    pagination: PaginationInfo

