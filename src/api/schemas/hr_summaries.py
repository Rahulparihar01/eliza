"""
Pydantic schemas for HR Summary Views API endpoints.
Defines response models for executive-level HR insights.
"""

from pydantic import BaseModel, Field
from typing import List, Optional, Dict, Any
from datetime import datetime


# ============================================================================
# Employee Overview Summary Schemas
# ============================================================================

class DepartmentBreakdown(BaseModel):
    """Department employee breakdown"""
    department_id: int = Field(..., description="Department ID")
    department_name: str = Field(..., description="Department name")
    employee_count: int = Field(..., description="Number of active employees")


class PositionBreakdown(BaseModel):
    """Position employee breakdown"""
    position_id: int = Field(..., description="Position ID")
    position_title: str = Field(..., description="Position title")
    position_level: str = Field(..., description="Position level")
    employee_count: int = Field(..., description="Number of active employees")


class EmployeeOverviewSummary(BaseModel):
    """Employee overview summary for executives"""
    customer_id: str = Field(..., description="Customer ID")
    total_employees: int = Field(..., description="Total number of employees")
    active_employees: int = Field(..., description="Number of active employees")
    on_leave_employees: int = Field(..., description="Number of employees on leave")
    terminated_employees: int = Field(..., description="Number of terminated employees")
    full_time_employees: int = Field(..., description="Number of full-time employees")
    part_time_employees: int = Field(..., description="Number of part-time employees")
    contractor_employees: int = Field(..., description="Number of contractors")
    office_employees: int = Field(..., description="Number of office-based employees")
    remote_employees: int = Field(..., description="Number of remote employees")
    hybrid_employees: int = Field(..., description="Number of hybrid employees")
    total_departments: int = Field(..., description="Total number of departments")
    total_positions: int = Field(..., description="Total number of positions")
    avg_tenure_years: Optional[float] = Field(None, description="Average employee tenure in years")
    department_breakdown: List[DepartmentBreakdown] = Field(default_factory=list, description="Employees by department")
    position_breakdown: List[PositionBreakdown] = Field(default_factory=list, description="Employees by position")

    class Config:
        from_attributes = True
        json_schema_extra = {
            "example": {
                "customer_id": "eliza",
                "total_employees": 150,
                "active_employees": 142,
                "on_leave_employees": 5,
                "terminated_employees": 3,
                "full_time_employees": 130,
                "part_time_employees": 10,
                "contractor_employees": 10,
                "office_employees": 50,
                "remote_employees": 60,
                "hybrid_employees": 40,
                "total_departments": 8,
                "total_positions": 25,
                "avg_tenure_years": 3.5,
                "department_breakdown": [
                    {"department_id": 1, "department_name": "Engineering", "employee_count": 45},
                    {"department_id": 2, "department_name": "Sales", "employee_count": 30}
                ],
                "position_breakdown": [
                    {"position_id": 1, "position_title": "Software Engineer", "position_level": "Mid", "employee_count": 25}
                ]
            }
        }


# ============================================================================
# Skills & Competencies Summary Schemas
# ============================================================================

class SkillBreakdown(BaseModel):
    """Skill distribution breakdown"""
    skill_id: int = Field(..., description="Skill ID")
    skill_name: str = Field(..., description="Skill name")
    skill_category: str = Field(..., description="Skill category")
    employee_count: int = Field(..., description="Number of employees with this skill")
    avg_proficiency: Optional[float] = Field(None, description="Average proficiency level (1-4)")


class CategoryBreakdown(BaseModel):
    """Skill category breakdown"""
    category: str = Field(..., description="Skill category")
    skill_count: int = Field(..., description="Number of skills in category")
    employee_count: int = Field(..., description="Number of employees with skills in category")


class SkillsCompetenciesSummary(BaseModel):
    """Skills and competencies summary for executives"""
    customer_id: str = Field(..., description="Customer ID")
    total_skills: int = Field(..., description="Total number of unique skills")
    total_skill_assignments: int = Field(..., description="Total skill-employee assignments")
    employees_with_skills: int = Field(..., description="Number of employees with at least one skill")
    expert_level_skills: int = Field(..., description="Number of expert-level skill assignments")
    advanced_level_skills: int = Field(..., description="Number of advanced-level skill assignments")
    intermediate_level_skills: int = Field(..., description="Number of intermediate-level skill assignments")
    beginner_level_skills: int = Field(..., description="Number of beginner-level skill assignments")
    avg_years_experience: Optional[float] = Field(None, description="Average years of experience across all skills")
    skill_breakdown: List[SkillBreakdown] = Field(default_factory=list, description="Skills distribution")
    category_breakdown: List[CategoryBreakdown] = Field(default_factory=list, description="Skills by category")

    class Config:
        from_attributes = True
        json_schema_extra = {
            "example": {
                "customer_id": "eliza",
                "total_skills": 85,
                "total_skill_assignments": 420,
                "employees_with_skills": 140,
                "expert_level_skills": 95,
                "advanced_level_skills": 150,
                "intermediate_level_skills": 120,
                "beginner_level_skills": 55,
                "avg_years_experience": 4.2,
                "skill_breakdown": [
                    {"skill_id": 1, "skill_name": "Python", "skill_category": "Programming", "employee_count": 45, "avg_proficiency": 3.2}
                ],
                "category_breakdown": [
                    {"category": "Programming", "skill_count": 15, "employee_count": 60}
                ]
            }
        }


# ============================================================================
# Performance & Development Summary Schemas
# ============================================================================

class DepartmentPerformance(BaseModel):
    """Department performance metrics"""
    department_id: int = Field(..., description="Department ID")
    department_name: str = Field(..., description="Department name")
    avg_rating: Optional[float] = Field(None, description="Average performance rating")
    promotion_ready_count: int = Field(..., description="Number of employees ready for promotion")


class TrainingProgramStats(BaseModel):
    """Training program statistics"""
    training_program_id: int = Field(..., description="Training program ID")
    program_name: str = Field(..., description="Program name")
    completion_count: int = Field(..., description="Number of completions")
    avg_rating: Optional[float] = Field(None, description="Average feedback rating")


class PerformanceDevelopmentSummary(BaseModel):
    """Performance and development summary for executives"""
    customer_id: str = Field(..., description="Customer ID")
    total_active_employees: int = Field(..., description="Total active employees")
    total_performance_reviews: int = Field(..., description="Total performance reviews")
    reviews_last_12_months: int = Field(..., description="Reviews in last 12 months")
    avg_overall_rating: Optional[float] = Field(None, description="Average overall performance rating")
    ready_for_promotion: int = Field(..., description="Employees ready for promotion now")
    ready_in_6_months: int = Field(..., description="Employees ready for promotion in 6 months")
    ready_in_12_months: int = Field(..., description="Employees ready for promotion in 12 months")
    total_training_records: int = Field(..., description="Total training records")
    completed_trainings: int = Field(..., description="Completed training sessions")
    in_progress_trainings: int = Field(..., description="In-progress training sessions")
    enrolled_trainings: int = Field(..., description="Enrolled training sessions")
    avg_training_rating: Optional[float] = Field(None, description="Average training feedback rating")
    avg_goals_achievement: Optional[float] = Field(None, description="Average goals achievement percentage")
    department_performance: List[DepartmentPerformance] = Field(default_factory=list, description="Performance by department")
    training_program_stats: List[TrainingProgramStats] = Field(default_factory=list, description="Training program statistics")

    class Config:
        from_attributes = True
        json_schema_extra = {
            "example": {
                "customer_id": "eliza",
                "total_active_employees": 142,
                "total_performance_reviews": 285,
                "reviews_last_12_months": 140,
                "avg_overall_rating": 3.8,
                "ready_for_promotion": 12,
                "ready_in_6_months": 18,
                "ready_in_12_months": 25,
                "total_training_records": 450,
                "completed_trainings": 380,
                "in_progress_trainings": 45,
                "enrolled_trainings": 25,
                "avg_training_rating": 4.2,
                "avg_goals_achievement": 87.5,
                "department_performance": [
                    {"department_id": 1, "department_name": "Engineering", "avg_rating": 3.9, "promotion_ready_count": 5}
                ],
                "training_program_stats": [
                    {"training_program_id": 1, "program_name": "Leadership Development", "completion_count": 45, "avg_rating": 4.5}
                ]
            }
        }


# ============================================================================
# All Tables List Schema
# ============================================================================

class HRTableInfo(BaseModel):
    """Information about an HR table"""
    table_name: str = Field(..., description="Table name")
    display_name: str = Field(..., description="Human-readable table name")
    description: str = Field(..., description="Table description")
    record_count: int = Field(..., description="Number of records")
    last_updated: Optional[datetime] = Field(None, description="Last update timestamp")


class HRTablesListResponse(BaseModel):
    """List of all HR tables"""
    tables: List[HRTableInfo] = Field(..., description="List of HR tables")
    total_tables: int = Field(..., description="Total number of tables")

    class Config:
        json_schema_extra = {
            "example": {
                "tables": [
                    {
                        "table_name": "hr_employees",
                        "display_name": "Employees",
                        "description": "Employee records",
                        "record_count": 150,
                        "last_updated": "2025-10-01T12:00:00Z"
                    }
                ],
                "total_tables": 15
            }
        }

