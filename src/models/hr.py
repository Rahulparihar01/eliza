"""
HR Data Models for Employee Management System.

This module contains SQLAlchemy models for comprehensive HR data management including:
- Employee records and organizational structure
- Skills and certifications
- Performance reviews and goals
- Training and learning paths
- Compensation (encrypted)
- Time off management
"""

from datetime import datetime, date
from typing import Optional, List
from sqlalchemy import (
    Column, Integer, String, Boolean, DateTime, Date, Float, Text,
    ForeignKey, JSON, Numeric, Enum as SQLEnum, Index, UniqueConstraint
)
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
import enum

from src.models.database import Base
from src.utils.encryption import EncryptedString


# Enums for type safety
class EmploymentStatus(str, enum.Enum):
    """Employment status options."""
    ACTIVE = "active"
    ON_LEAVE = "on_leave"
    TERMINATED = "terminated"
    RETIRED = "retired"


class EmploymentType(str, enum.Enum):
    """Employment type options."""
    FULL_TIME = "full_time"
    PART_TIME = "part_time"
    CONTRACTOR = "contractor"
    INTERN = "intern"


class WorkLocation(str, enum.Enum):
    """Work location options."""
    OFFICE = "office"
    REMOTE = "remote"
    HYBRID = "hybrid"


class ChangeType(str, enum.Enum):
    """Employment change type options."""
    HIRE = "hire"
    PROMOTION = "promotion"
    TRANSFER = "transfer"
    DEMOTION = "demotion"
    TERMINATION = "termination"
    ROLE_CHANGE = "role_change"


class ProficiencyLevel(str, enum.Enum):
    """Skill proficiency level options."""
    BEGINNER = "beginner"
    INTERMEDIATE = "intermediate"
    ADVANCED = "advanced"
    EXPERT = "expert"


class TrainingStatus(str, enum.Enum):
    """Training status options."""
    ENROLLED = "enrolled"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class ReviewStatus(str, enum.Enum):
    """Performance review status options."""
    DRAFT = "draft"
    PENDING_EMPLOYEE_REVIEW = "pending_employee_review"
    PENDING_MANAGER_APPROVAL = "pending_manager_approval"
    COMPLETED = "completed"
    ARCHIVED = "archived"


class TimeOffStatus(str, enum.Enum):
    """Time off request status options."""
    PENDING = "pending"
    APPROVED = "approved"
    DENIED = "denied"
    CANCELLED = "cancelled"


# ============================================================================
# CORE HR MODELS
# ============================================================================

class Department(Base):
    """Department organizational structure."""
    
    __tablename__ = 'hr_departments'
    __table_args__ = (
        Index('idx_hr_departments_customer', 'customer_id'),
        Index('idx_hr_departments_parent', 'parent_department_id'),
        {'extend_existing': True}
    )
    
    id = Column(Integer, primary_key=True, index=True)
    customer_id = Column(String(100), nullable=False, index=True)  # Tenant identifier for data isolation
    name = Column(String(255), nullable=False)
    code = Column(String(50), nullable=False)  # e.g., "ENG", "HR"
    description = Column(Text, nullable=True)
    parent_department_id = Column(Integer, ForeignKey('hr_departments.id'), nullable=True)
    head_employee_id = Column(Integer, ForeignKey('hr_employees.id'), nullable=True)
    cost_center = Column(String(100), nullable=True)
    is_active = Column(Boolean, default=True, nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)
    
    # Relationships
    parent_department = relationship("Department", remote_side=[id], backref="child_departments")
    head_employee = relationship("Employee", foreign_keys=[head_employee_id], backref="headed_department")
    employees = relationship("Employee", foreign_keys="Employee.department_id", back_populates="department")


class Position(Base):
    """Job positions/titles."""
    
    __tablename__ = 'hr_positions'
    __table_args__ = (
        Index('idx_hr_positions_customer', 'customer_id'),
        Index('idx_hr_positions_level', 'level'),
        {'extend_existing': True}
    )
    
    id = Column(Integer, primary_key=True, index=True)
    customer_id = Column(String(100), nullable=False, index=True)  # Tenant identifier for data isolation
    title = Column(String(255), nullable=False)
    level = Column(String(50), nullable=False)  # entry, mid, senior, lead, principal, director, vp, c_level
    job_family = Column(String(100), nullable=False)  # engineering, sales, operations, etc.
    description = Column(Text, nullable=True)
    required_skills = Column(JSON, nullable=True)  # Array of skill IDs
    is_active = Column(Boolean, default=True, nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)
    
    # Relationships
    employees = relationship("Employee", back_populates="position")


class Employee(Base):
    """Core employee record."""
    
    __tablename__ = 'hr_employees'
    __table_args__ = (
        Index('idx_hr_employees_customer', 'customer_id'),
        Index('idx_hr_employees_user', 'user_id'),
        Index('idx_hr_employees_manager', 'manager_id'),
        Index('idx_hr_employees_status', 'employment_status'),
        UniqueConstraint('customer_id', 'employee_number', name='uq_employee_number_per_customer'),
        {'extend_existing': True}
    )
    
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey('users.id'), nullable=True)  # Links to auth system
    customer_id = Column(String(100), nullable=False, index=True)  # Tenant identifier for data isolation
    employee_number = Column(String(50), nullable=False)  # Unique per customer
    hire_date = Column(Date, nullable=False)
    employment_status = Column(SQLEnum(EmploymentStatus, values_callable=lambda x: [e.value for e in x]), nullable=False, default=EmploymentStatus.ACTIVE)
    employment_type = Column(SQLEnum(EmploymentType, values_callable=lambda x: [e.value for e in x]), nullable=False, default=EmploymentType.FULL_TIME)
    work_location = Column(SQLEnum(WorkLocation, values_callable=lambda x: [e.value for e in x]), nullable=False, default=WorkLocation.HYBRID)
    manager_id = Column(Integer, ForeignKey('hr_employees.id'), nullable=True)
    position_id = Column(Integer, ForeignKey('hr_positions.id'), nullable=False)
    department_id = Column(Integer, ForeignKey('hr_departments.id'), nullable=False)
    
    # Personal info (duplicated from users for data ingestion flexibility)
    first_name = Column(String(100), nullable=False)
    last_name = Column(String(100), nullable=False)
    email = Column(String(255), nullable=False, index=True)
    phone = Column(String(50), nullable=True)
    
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)
    
    # Relationships
    manager = relationship("Employee", remote_side=[id], backref="direct_reports")
    position = relationship("Position", back_populates="employees")
    department = relationship("Department", foreign_keys=[department_id], back_populates="employees")
    skills = relationship("EmployeeSkill", foreign_keys="EmployeeSkill.employee_id", back_populates="employee", cascade="all, delete-orphan")
    certifications = relationship("Certification", back_populates="employee", cascade="all, delete-orphan")
    employment_history = relationship("EmploymentHistory", back_populates="employee", cascade="all, delete-orphan")
    compensation_records = relationship("Compensation", back_populates="employee", cascade="all, delete-orphan")
    performance_reviews = relationship("PerformanceReview", foreign_keys="PerformanceReview.employee_id", back_populates="employee")
    training_records = relationship("EmployeeTrainingRecord", back_populates="employee", cascade="all, delete-orphan")
    learning_paths = relationship("EmployeeLearningPath", foreign_keys="EmployeeLearningPath.employee_id", back_populates="employee", cascade="all, delete-orphan")
    time_off_requests = relationship("TimeOffRequest", foreign_keys="TimeOffRequest.employee_id", back_populates="employee", cascade="all, delete-orphan")
    emergency_contacts = relationship("EmergencyContact", back_populates="employee", cascade="all, delete-orphan")
    performance_goals = relationship("PerformanceGoal", back_populates="employee", cascade="all, delete-orphan")
    
    @property
    def full_name(self) -> str:
        """Get employee's full name."""
        return f"{self.first_name} {self.last_name}"


class EmploymentHistory(Base):
    """Track employment changes over time."""
    
    __tablename__ = 'hr_employment_history'
    __table_args__ = (
        Index('idx_hr_employment_history_employee', 'employee_id'),
        Index('idx_hr_employment_history_dates', 'start_date', 'end_date'),
        {'extend_existing': True}
    )
    
    id = Column(Integer, primary_key=True, index=True)
    employee_id = Column(Integer, ForeignKey('hr_employees.id'), nullable=False)
    customer_id = Column(String(100), nullable=False, index=True)  # Tenant identifier for data isolation
    position_id = Column(Integer, ForeignKey('hr_positions.id'), nullable=False)
    department_id = Column(Integer, ForeignKey('hr_departments.id'), nullable=False)
    start_date = Column(Date, nullable=False)
    end_date = Column(Date, nullable=True)  # NULL if current
    change_type = Column(SQLEnum(ChangeType, values_callable=lambda x: [e.value for e in x]), nullable=False)
    change_reason = Column(String(500), nullable=True)
    notes = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    
    # Relationships
    employee = relationship("Employee", back_populates="employment_history")
    position = relationship("Position")
    department = relationship("Department")


class Compensation(Base):
    """Compensation records (encrypted sensitive data)."""
    
    __tablename__ = 'hr_compensation'
    __table_args__ = (
        Index('idx_hr_compensation_employee', 'employee_id'),
        Index('idx_hr_compensation_effective_date', 'effective_date'),
        {'extend_existing': True}
    )
    
    id = Column(Integer, primary_key=True, index=True)
    employee_id = Column(Integer, ForeignKey('hr_employees.id'), nullable=False)
    customer_id = Column(String(100), nullable=False, index=True)  # Tenant identifier for data isolation
    effective_date = Column(Date, nullable=False)
    salary_amount = Column(EncryptedString(255), nullable=False)  # Encrypted
    salary_currency = Column(String(10), nullable=False, default='USD')
    pay_frequency = Column(String(50), nullable=False)  # annual, monthly, hourly
    bonus_eligible = Column(Boolean, default=False)
    equity_granted = Column(String(255), nullable=True)
    compensation_notes = Column(EncryptedString(1000), nullable=True)  # Encrypted
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)
    
    # Relationships
    employee = relationship("Employee", back_populates="compensation_records")


# ============================================================================
# SKILLS & CERTIFICATIONS MODELS
# ============================================================================

class Skill(Base):
    """Skills catalog."""

    __tablename__ = 'hr_skills'
    __table_args__ = (
        Index('idx_hr_skills_customer', 'customer_id'),
        Index('idx_hr_skills_category', 'category'),
        {'extend_existing': True}
    )

    id = Column(Integer, primary_key=True, index=True)
    customer_id = Column(String(100), nullable=True, index=True)  # NULL for global skills, tenant identifier for custom skills
    name = Column(String(255), nullable=False)
    category = Column(String(100), nullable=False)  # technical, soft_skill, language, certification
    description = Column(Text, nullable=True)
    is_active = Column(Boolean, default=True, nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)

    # Relationships
    employee_skills = relationship("EmployeeSkill", back_populates="skill", cascade="all, delete-orphan")


class EmployeeSkill(Base):
    """Employee-skill mapping with proficiency."""

    __tablename__ = 'hr_employee_skills'
    __table_args__ = (
        Index('idx_hr_employee_skills_employee', 'employee_id'),
        Index('idx_hr_employee_skills_skill', 'skill_id'),
        UniqueConstraint('employee_id', 'skill_id', name='uq_employee_skill'),
        {'extend_existing': True}
    )

    id = Column(Integer, primary_key=True, index=True)
    employee_id = Column(Integer, ForeignKey('hr_employees.id'), nullable=False)
    skill_id = Column(Integer, ForeignKey('hr_skills.id'), nullable=False)
    customer_id = Column(String(100), nullable=False, index=True)  # Tenant identifier for data isolation
    proficiency_level = Column(SQLEnum(ProficiencyLevel, values_callable=lambda x: [e.value for e in x]), nullable=False)
    years_experience = Column(Float, nullable=True)
    last_used_date = Column(Date, nullable=True)
    verified_by_employee_id = Column(Integer, ForeignKey('hr_employees.id'), nullable=True)
    verified_at = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)

    # Relationships
    employee = relationship("Employee", foreign_keys=[employee_id], back_populates="skills", overlaps="verified_by")
    skill = relationship("Skill", back_populates="employee_skills")
    verified_by = relationship("Employee", foreign_keys=[verified_by_employee_id], overlaps="employee")


class Certification(Base):
    """Professional certifications."""

    __tablename__ = 'hr_certifications'
    __table_args__ = (
        Index('idx_hr_certifications_employee', 'employee_id'),
        Index('idx_hr_certifications_status', 'status'),
        Index('idx_hr_certifications_expiration', 'expiration_date'),
        {'extend_existing': True}
    )

    id = Column(Integer, primary_key=True, index=True)
    employee_id = Column(Integer, ForeignKey('hr_employees.id'), nullable=False)
    customer_id = Column(String(100), nullable=False, index=True)  # Tenant identifier for data isolation
    certification_name = Column(String(255), nullable=False)
    issuing_organization = Column(String(255), nullable=False)
    certification_number = Column(String(255), nullable=True)
    issue_date = Column(Date, nullable=False)
    expiration_date = Column(Date, nullable=True)
    verification_url = Column(String(500), nullable=True)
    status = Column(String(50), nullable=False, default='active')  # active, expired, revoked
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)

    # Relationships
    employee = relationship("Employee", back_populates="certifications")


class CompetencyFramework(Base):
    """Define competencies per position/level."""

    __tablename__ = 'hr_competency_framework'
    __table_args__ = (
        Index('idx_hr_competency_framework_customer', 'customer_id'),
        Index('idx_hr_competency_framework_type', 'competency_type'),
        {'extend_existing': True}
    )

    id = Column(Integer, primary_key=True, index=True)
    customer_id = Column(String(100), nullable=False, index=True)  # Tenant identifier for data isolation
    competency_name = Column(String(255), nullable=False)
    competency_type = Column(String(100), nullable=False)  # technical, behavioral, leadership
    description = Column(Text, nullable=True)
    applicable_positions = Column(JSON, nullable=True)  # Array of position IDs
    applicable_levels = Column(JSON, nullable=True)  # Array of levels
    proficiency_levels = Column(JSON, nullable=True)  # Definitions for each rating level
    is_active = Column(Boolean, default=True, nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)


# ============================================================================
# PERFORMANCE MANAGEMENT MODELS
# ============================================================================

class PerformanceReview(Base):
    """Comprehensive performance reviews."""

    __tablename__ = 'hr_performance_reviews'
    __table_args__ = (
        Index('idx_hr_performance_reviews_employee', 'employee_id'),
        Index('idx_hr_performance_reviews_reviewer', 'reviewer_id'),
        Index('idx_hr_performance_reviews_period', 'review_period_start', 'review_period_end'),
        Index('idx_hr_performance_reviews_status', 'status'),
        {'extend_existing': True}
    )

    id = Column(Integer, primary_key=True, index=True)
    employee_id = Column(Integer, ForeignKey('hr_employees.id'), nullable=False)
    reviewer_id = Column(Integer, ForeignKey('hr_employees.id'), nullable=False)
    customer_id = Column(String(100), nullable=False, index=True)  # Tenant identifier for data isolation
    review_period_start = Column(Date, nullable=False)
    review_period_end = Column(Date, nullable=False)
    review_type = Column(String(50), nullable=False)  # annual, quarterly, probation, project, 360
    review_cycle = Column(String(50), nullable=False)  # e.g., "2025-Q1", "2025-Annual"

    # Overall Assessment
    overall_rating = Column(Float, nullable=True)  # 1-5 scale
    overall_summary = Column(Text, nullable=True)
    promotion_recommended = Column(Boolean, default=False)
    promotion_readiness = Column(String(50), nullable=True)  # not_ready, ready_6_months, ready_now

    # Competencies (JSON structure)
    technical_competencies = Column(JSON, nullable=True)  # {competency_name: rating}
    behavioral_competencies = Column(JSON, nullable=True)
    leadership_competencies = Column(JSON, nullable=True)

    # Goals & Objectives
    previous_goals = Column(JSON, nullable=True)  # Array of goal objects
    goals_achievement_percentage = Column(Float, nullable=True)
    new_goals = Column(JSON, nullable=True)
    okrs = Column(JSON, nullable=True)  # Objectives and Key Results
    kpis = Column(JSON, nullable=True)  # Key Performance Indicators

    # Development
    strengths = Column(Text, nullable=True)
    areas_for_improvement = Column(Text, nullable=True)
    development_plan = Column(JSON, nullable=True)
    recommended_training = Column(JSON, nullable=True)  # Array of training_program_ids

    # Additional Feedback
    peer_feedback = Column(JSON, nullable=True)  # Array for 360 reviews
    self_assessment = Column(JSON, nullable=True)
    manager_comments = Column(Text, nullable=True)

    # Workflow
    status = Column(SQLEnum(ReviewStatus, values_callable=lambda x: [e.value for e in x]), nullable=False, default=ReviewStatus.DRAFT)
    employee_acknowledged_at = Column(DateTime(timezone=True), nullable=True)
    manager_approved_at = Column(DateTime(timezone=True), nullable=True)
    hr_reviewed_at = Column(DateTime(timezone=True), nullable=True)

    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)

    # Relationships
    employee = relationship("Employee", foreign_keys=[employee_id], back_populates="performance_reviews")
    reviewer = relationship("Employee", foreign_keys=[reviewer_id])
    goals = relationship("PerformanceGoal", back_populates="performance_review", cascade="all, delete-orphan")


class PerformanceGoal(Base):
    """Detailed goal tracking."""

    __tablename__ = 'hr_performance_goals'
    __table_args__ = (
        Index('idx_hr_performance_goals_employee', 'employee_id'),
        Index('idx_hr_performance_goals_review', 'performance_review_id'),
        Index('idx_hr_performance_goals_status', 'status'),
        {'extend_existing': True}
    )

    id = Column(Integer, primary_key=True, index=True)
    employee_id = Column(Integer, ForeignKey('hr_employees.id'), nullable=False)
    performance_review_id = Column(Integer, ForeignKey('hr_performance_reviews.id'), nullable=True)  # Can exist outside reviews
    customer_id = Column(String(100), nullable=False, index=True)  # Tenant identifier for data isolation
    goal_title = Column(String(500), nullable=False)
    goal_description = Column(Text, nullable=True)
    goal_type = Column(String(50), nullable=False)  # individual, team, company
    category = Column(String(50), nullable=False)  # performance, development, project, okr
    target_completion_date = Column(Date, nullable=True)
    actual_completion_date = Column(Date, nullable=True)
    status = Column(String(50), nullable=False, default='not_started')  # not_started, in_progress, completed, cancelled, missed
    progress_percentage = Column(Float, nullable=True, default=0.0)
    success_criteria = Column(JSON, nullable=True)
    measurement_method = Column(String(500), nullable=True)
    weight_percentage = Column(Float, nullable=True)  # For weighted scoring
    final_rating = Column(Float, nullable=True)  # 1-5
    notes = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)

    # Relationships
    employee = relationship("Employee", back_populates="performance_goals")
    performance_review = relationship("PerformanceReview", back_populates="goals")


# ============================================================================
# TRAINING & LEARNING MODELS
# ============================================================================

class TrainingProgram(Base):
    """Training programs catalog."""

    __tablename__ = 'hr_training_programs'
    __table_args__ = (
        Index('idx_hr_training_programs_customer', 'customer_id'),
        Index('idx_hr_training_programs_category', 'category'),
        {'extend_existing': True}
    )

    id = Column(Integer, primary_key=True, index=True)
    customer_id = Column(String(100), nullable=False, index=True)  # Tenant identifier for data isolation
    program_name = Column(String(255), nullable=False)
    program_code = Column(String(50), nullable=False)
    provider = Column(String(255), nullable=False)  # internal, external, vendor_name
    category = Column(String(100), nullable=False)  # technical, leadership, compliance, soft_skills
    description = Column(Text, nullable=True)
    duration_hours = Column(Float, nullable=True)
    delivery_method = Column(String(50), nullable=False)  # in_person, virtual, self_paced, hybrid
    cost_per_participant = Column(Numeric(10, 2), nullable=True)
    required_for_positions = Column(JSON, nullable=True)  # Array of position IDs
    is_mandatory = Column(Boolean, default=False)
    is_active = Column(Boolean, default=True, nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)

    # Relationships
    training_records = relationship("EmployeeTrainingRecord", back_populates="training_program", cascade="all, delete-orphan")


class EmployeeTrainingRecord(Base):
    """Training completion tracking."""

    __tablename__ = 'hr_employee_training_records'
    __table_args__ = (
        Index('idx_hr_employee_training_records_employee', 'employee_id'),
        Index('idx_hr_employee_training_records_program', 'training_program_id'),
        Index('idx_hr_employee_training_records_status', 'status'),
        {'extend_existing': True}
    )

    id = Column(Integer, primary_key=True, index=True)
    employee_id = Column(Integer, ForeignKey('hr_employees.id'), nullable=False)
    training_program_id = Column(Integer, ForeignKey('hr_training_programs.id'), nullable=False)
    customer_id = Column(String(100), nullable=False, index=True)  # Tenant identifier for data isolation
    enrollment_date = Column(Date, nullable=False)
    start_date = Column(Date, nullable=True)
    completion_date = Column(Date, nullable=True)
    status = Column(SQLEnum(TrainingStatus, values_callable=lambda x: [e.value for e in x]), nullable=False, default=TrainingStatus.ENROLLED)
    score = Column(Float, nullable=True)  # If applicable
    certification_earned = Column(Boolean, default=False)
    certification_id = Column(Integer, ForeignKey('hr_certifications.id'), nullable=True)
    instructor_name = Column(String(255), nullable=True)
    cost_actual = Column(Numeric(10, 2), nullable=True)
    feedback_rating = Column(Float, nullable=True)  # 1-5
    feedback_comments = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)

    # Relationships
    employee = relationship("Employee", back_populates="training_records")
    training_program = relationship("TrainingProgram", back_populates="training_records")
    certification = relationship("Certification")


class LearningPath(Base):
    """Career development paths."""

    __tablename__ = 'hr_learning_paths'
    __table_args__ = (
        Index('idx_hr_learning_paths_customer', 'customer_id'),
        Index('idx_hr_learning_paths_target_position', 'target_position_id'),
        {'extend_existing': True}
    )

    id = Column(Integer, primary_key=True, index=True)
    customer_id = Column(String(100), nullable=False, index=True)  # Tenant identifier for data isolation
    path_name = Column(String(255), nullable=False)
    target_position_id = Column(Integer, ForeignKey('hr_positions.id'), nullable=False)
    description = Column(Text, nullable=True)
    estimated_duration_months = Column(Integer, nullable=True)
    required_training_programs = Column(JSON, nullable=True)  # Array of training_program_ids
    required_skills = Column(JSON, nullable=True)  # Array of skill_ids
    is_active = Column(Boolean, default=True, nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)

    # Relationships
    target_position = relationship("Position")
    employee_learning_paths = relationship("EmployeeLearningPath", back_populates="learning_path", cascade="all, delete-orphan")


class EmployeeLearningPath(Base):
    """Employee progress on learning paths."""

    __tablename__ = 'hr_employee_learning_paths'
    __table_args__ = (
        Index('idx_hr_employee_learning_paths_employee', 'employee_id'),
        Index('idx_hr_employee_learning_paths_path', 'learning_path_id'),
        {'extend_existing': True}
    )

    id = Column(Integer, primary_key=True, index=True)
    employee_id = Column(Integer, ForeignKey('hr_employees.id'), nullable=False)
    learning_path_id = Column(Integer, ForeignKey('hr_learning_paths.id'), nullable=False)
    customer_id = Column(String(100), nullable=False, index=True)  # Tenant identifier for data isolation
    start_date = Column(Date, nullable=False)
    target_completion_date = Column(Date, nullable=True)
    actual_completion_date = Column(Date, nullable=True)
    progress_percentage = Column(Float, nullable=True, default=0.0)
    status = Column(String(50), nullable=False, default='not_started')  # not_started, in_progress, completed, abandoned
    assigned_by_employee_id = Column(Integer, ForeignKey('hr_employees.id'), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)

    # Relationships
    employee = relationship("Employee", foreign_keys=[employee_id], back_populates="learning_paths", overlaps="assigned_by")
    learning_path = relationship("LearningPath", back_populates="employee_learning_paths")
    assigned_by = relationship("Employee", foreign_keys=[assigned_by_employee_id], overlaps="employee")
    assigned_by = relationship("Employee", foreign_keys=[assigned_by_employee_id])


# ============================================================================
# TIME OFF & EMERGENCY CONTACTS MODELS
# ============================================================================

class TimeOffRequest(Base):
    """PTO/Leave tracking."""

    __tablename__ = 'hr_time_off_requests'
    __table_args__ = (
        Index('idx_hr_time_off_requests_employee', 'employee_id'),
        Index('idx_hr_time_off_requests_dates', 'start_date', 'end_date'),
        Index('idx_hr_time_off_requests_status', 'status'),
        {'extend_existing': True}
    )

    id = Column(Integer, primary_key=True, index=True)
    employee_id = Column(Integer, ForeignKey('hr_employees.id'), nullable=False)
    customer_id = Column(String(100), nullable=False, index=True)  # Tenant identifier for data isolation
    request_type = Column(String(50), nullable=False)  # vacation, sick, personal, parental, etc.
    start_date = Column(Date, nullable=False)
    end_date = Column(Date, nullable=False)
    total_days = Column(Float, nullable=False)
    status = Column(SQLEnum(TimeOffStatus, values_callable=lambda x: [e.value for e in x]), nullable=False, default=TimeOffStatus.PENDING)
    approved_by_employee_id = Column(Integer, ForeignKey('hr_employees.id'), nullable=True)
    approved_at = Column(DateTime(timezone=True), nullable=True)
    notes = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)

    # Relationships
    employee = relationship("Employee", foreign_keys=[employee_id], back_populates="time_off_requests", overlaps="approved_by")
    approved_by = relationship("Employee", foreign_keys=[approved_by_employee_id], overlaps="employee")


class EmergencyContact(Base):
    """Emergency contact information."""

    __tablename__ = 'hr_emergency_contacts'
    __table_args__ = (
        Index('idx_hr_emergency_contacts_employee', 'employee_id'),
        {'extend_existing': True}
    )

    id = Column(Integer, primary_key=True, index=True)
    employee_id = Column(Integer, ForeignKey('hr_employees.id'), nullable=False)
    customer_id = Column(String(100), nullable=False, index=True)  # Tenant identifier for data isolation
    contact_name = Column(String(255), nullable=False)
    relationship_type = Column(String(100), nullable=False)  # spouse, parent, sibling, friend, etc.
    phone_primary = Column(String(50), nullable=False)
    phone_secondary = Column(String(50), nullable=True)
    email = Column(String(255), nullable=True)
    address = Column(JSON, nullable=True)  # {street, city, state, zip, country}
    is_primary_contact = Column(Boolean, default=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)

    # Relationships
    employee = relationship("Employee", back_populates="emergency_contacts")


# ============================================================================
# DATA PIPELINE SUPPORT MODELS
# ============================================================================

class HRDataFieldMapping(Base):
    """Field mapping configuration for data ingestion."""

    __tablename__ = 'hr_data_field_mappings'
    __table_args__ = (
        Index('idx_hr_data_field_mappings_customer', 'customer_id'),
        Index('idx_hr_data_field_mappings_source', 'source_system'),
        {'extend_existing': True}
    )

    id = Column(Integer, primary_key=True, index=True)
    customer_id = Column(String(100), nullable=False, index=True)  # Tenant identifier for data isolation
    source_system = Column(String(100), nullable=False)  # e.g., "Workday", "BambooHR"
    source_field_name = Column(String(255), nullable=False)
    target_table = Column(String(100), nullable=False)
    target_field_name = Column(String(100), nullable=False)
    transformation_rule = Column(JSON, nullable=True)  # e.g., date format conversion
    is_required = Column(Boolean, default=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)


class HRDataIngestionLog(Base):
    """Audit trail for data ingestion."""

    __tablename__ = 'hr_data_ingestion_logs'
    __table_args__ = (
        Index('idx_hr_data_ingestion_logs_customer', 'customer_id'),
        Index('idx_hr_data_ingestion_logs_batch', 'ingestion_batch_id'),
        Index('idx_hr_data_ingestion_logs_started', 'started_at'),
        {'extend_existing': True}
    )

    id = Column(Integer, primary_key=True, index=True)
    customer_id = Column(String(100), nullable=False, index=True)  # Tenant identifier for data isolation
    ingestion_batch_id = Column(String(100), nullable=False, index=True)
    source_system = Column(String(100), nullable=False)
    records_processed = Column(Integer, nullable=False, default=0)
    records_succeeded = Column(Integer, nullable=False, default=0)
    records_failed = Column(Integer, nullable=False, default=0)
    errors = Column(JSON, nullable=True)  # Array of error objects
    started_at = Column(DateTime(timezone=True), nullable=False)
    completed_at = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)


class HRDataValidationRule(Base):
    """Data quality validation rules."""

    __tablename__ = 'hr_data_validation_rules'
    __table_args__ = (
        Index('idx_hr_data_validation_rules_customer', 'customer_id'),
        Index('idx_hr_data_validation_rules_table', 'target_table'),
        {'extend_existing': True}
    )

    id = Column(Integer, primary_key=True, index=True)
    customer_id = Column(String(100), nullable=False, index=True)  # Tenant identifier for data isolation
    rule_name = Column(String(255), nullable=False)
    target_table = Column(String(100), nullable=False)
    target_field = Column(String(100), nullable=False)
    validation_type = Column(String(50), nullable=False)  # required, data_type, range, regex, business_rule
    validation_config = Column(JSON, nullable=False)  # Configuration for the validation
    error_message = Column(String(500), nullable=False)
    is_active = Column(Boolean, default=True, nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)

