"""add hr schema

Revision ID: 012_add_hr_schema
Revises: 001_initial_schema
Create Date: 2025-01-15 10:00:00.000000

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = '012_add_hr_schema'
down_revision = '001_initial_schema'
branch_labels = None
depends_on = None
tags = ["core"]


def upgrade() -> None:
    """Create HR schema tables."""

    # Create enum types - SQLAlchemy will handle creation with checkfirst=True
    # when the first table using each enum is created
    
    # 1. Departments
    op.create_table(
        'hr_departments',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('customer_id', sa.String(length=100), nullable=False),
        sa.Column('name', sa.String(length=255), nullable=False),
        sa.Column('code', sa.String(length=50), nullable=False),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('parent_department_id', sa.Integer(), nullable=True),
        sa.Column('head_employee_id', sa.Integer(), nullable=True),
        sa.Column('cost_center', sa.String(length=100), nullable=True),
        sa.Column('is_active', sa.Boolean(), nullable=False, server_default='true'),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.ForeignKeyConstraint(['parent_department_id'], ['hr_departments.id']),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('idx_hr_departments_customer', 'hr_departments', ['customer_id'])
    op.create_index('idx_hr_departments_parent', 'hr_departments', ['parent_department_id'])
    
    # 2. Positions
    op.create_table(
        'hr_positions',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('customer_id', sa.String(length=100), nullable=False),
        sa.Column('title', sa.String(length=255), nullable=False),
        sa.Column('level', sa.String(length=50), nullable=False),
        sa.Column('job_family', sa.String(length=100), nullable=False),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('required_skills', sa.JSON(), nullable=True),
        sa.Column('is_active', sa.Boolean(), nullable=False, server_default='true'),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('idx_hr_positions_customer', 'hr_positions', ['customer_id'])
    op.create_index('idx_hr_positions_level', 'hr_positions', ['level'])
    
    # 3. Employees
    op.create_table(
        'hr_employees',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('user_id', sa.Integer(), nullable=True),
        sa.Column('customer_id', sa.String(length=100), nullable=False),
        sa.Column('employee_number', sa.String(length=50), nullable=False),
        sa.Column('hire_date', sa.Date(), nullable=False),
        sa.Column('employment_status', sa.Enum('active', 'on_leave', 'terminated', 'retired', name='employmentstatus'), nullable=False),
        sa.Column('employment_type', sa.Enum('full_time', 'part_time', 'contractor', 'intern', name='employmenttype'), nullable=False),
        sa.Column('work_location', sa.Enum('office', 'remote', 'hybrid', name='worklocation'), nullable=False),
        sa.Column('manager_id', sa.Integer(), nullable=True),
        sa.Column('position_id', sa.Integer(), nullable=False),
        sa.Column('department_id', sa.Integer(), nullable=False),
        sa.Column('first_name', sa.String(length=100), nullable=False),
        sa.Column('last_name', sa.String(length=100), nullable=False),
        sa.Column('email', sa.String(length=255), nullable=False),
        sa.Column('phone', sa.String(length=50), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.ForeignKeyConstraint(['user_id'], ['users.id']),
        sa.ForeignKeyConstraint(['manager_id'], ['hr_employees.id']),
        sa.ForeignKeyConstraint(['position_id'], ['hr_positions.id']),
        sa.ForeignKeyConstraint(['department_id'], ['hr_departments.id']),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('customer_id', 'employee_number', name='uq_employee_number_per_customer')
    )
    op.create_index('idx_hr_employees_customer', 'hr_employees', ['customer_id'])
    op.create_index('idx_hr_employees_user', 'hr_employees', ['user_id'])
    op.create_index('idx_hr_employees_manager', 'hr_employees', ['manager_id'])
    op.create_index('idx_hr_employees_status', 'hr_employees', ['employment_status'])
    op.create_index('idx_hr_employees_email', 'hr_employees', ['email'])
    
    # Add foreign key for head_employee_id in departments (after employees table exists)
    op.create_foreign_key(
        'fk_hr_departments_head_employee',
        'hr_departments', 'hr_employees',
        ['head_employee_id'], ['id']
    )
    
    # 4. Employment History
    op.create_table(
        'hr_employment_history',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('employee_id', sa.Integer(), nullable=False),
        sa.Column('customer_id', sa.String(length=100), nullable=False),
        sa.Column('position_id', sa.Integer(), nullable=False),
        sa.Column('department_id', sa.Integer(), nullable=False),
        sa.Column('start_date', sa.Date(), nullable=False),
        sa.Column('end_date', sa.Date(), nullable=True),
        sa.Column('change_type', sa.Enum('hire', 'promotion', 'transfer', 'demotion', 'termination', 'role_change', name='changetype'), nullable=False),
        sa.Column('change_reason', sa.String(length=500), nullable=True),
        sa.Column('notes', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.ForeignKeyConstraint(['employee_id'], ['hr_employees.id']),
        sa.ForeignKeyConstraint(['position_id'], ['hr_positions.id']),
        sa.ForeignKeyConstraint(['department_id'], ['hr_departments.id']),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('idx_hr_employment_history_employee', 'hr_employment_history', ['employee_id'])
    op.create_index('idx_hr_employment_history_dates', 'hr_employment_history', ['start_date', 'end_date'])
    
    # 5. Compensation
    op.create_table(
        'hr_compensation',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('employee_id', sa.Integer(), nullable=False),
        sa.Column('customer_id', sa.String(length=100), nullable=False),
        sa.Column('effective_date', sa.Date(), nullable=False),
        sa.Column('salary_amount', sa.String(length=255), nullable=False),  # Encrypted
        sa.Column('salary_currency', sa.String(length=10), nullable=False, server_default='USD'),
        sa.Column('pay_frequency', sa.String(length=50), nullable=False),
        sa.Column('bonus_eligible', sa.Boolean(), nullable=False, server_default='false'),
        sa.Column('equity_granted', sa.String(length=255), nullable=True),
        sa.Column('compensation_notes', sa.String(length=1000), nullable=True),  # Encrypted
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.ForeignKeyConstraint(['employee_id'], ['hr_employees.id']),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('idx_hr_compensation_employee', 'hr_compensation', ['employee_id'])
    op.create_index('idx_hr_compensation_effective_date', 'hr_compensation', ['effective_date'])
    
    # 6. Skills
    op.create_table(
        'hr_skills',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('customer_id', sa.String(length=100), nullable=True),
        sa.Column('name', sa.String(length=255), nullable=False),
        sa.Column('category', sa.String(length=100), nullable=False),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('is_active', sa.Boolean(), nullable=False, server_default='true'),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('idx_hr_skills_customer', 'hr_skills', ['customer_id'])
    op.create_index('idx_hr_skills_category', 'hr_skills', ['category'])
    
    # 7. Employee Skills
    op.create_table(
        'hr_employee_skills',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('employee_id', sa.Integer(), nullable=False),
        sa.Column('skill_id', sa.Integer(), nullable=False),
        sa.Column('customer_id', sa.String(length=100), nullable=False),
        sa.Column('proficiency_level', sa.Enum('beginner', 'intermediate', 'advanced', 'expert', name='proficiencylevel'), nullable=False),
        sa.Column('years_experience', sa.Float(), nullable=True),
        sa.Column('last_used_date', sa.Date(), nullable=True),
        sa.Column('verified_by_employee_id', sa.Integer(), nullable=True),
        sa.Column('verified_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.ForeignKeyConstraint(['employee_id'], ['hr_employees.id']),
        sa.ForeignKeyConstraint(['skill_id'], ['hr_skills.id']),
        sa.ForeignKeyConstraint(['verified_by_employee_id'], ['hr_employees.id']),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('employee_id', 'skill_id', name='uq_employee_skill')
    )
    op.create_index('idx_hr_employee_skills_employee', 'hr_employee_skills', ['employee_id'])
    op.create_index('idx_hr_employee_skills_skill', 'hr_employee_skills', ['skill_id'])
    
    # 8. Certifications
    op.create_table(
        'hr_certifications',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('employee_id', sa.Integer(), nullable=False),
        sa.Column('customer_id', sa.String(length=100), nullable=False),
        sa.Column('certification_name', sa.String(length=255), nullable=False),
        sa.Column('issuing_organization', sa.String(length=255), nullable=False),
        sa.Column('certification_number', sa.String(length=255), nullable=True),
        sa.Column('issue_date', sa.Date(), nullable=False),
        sa.Column('expiration_date', sa.Date(), nullable=True),
        sa.Column('verification_url', sa.String(length=500), nullable=True),
        sa.Column('status', sa.String(length=50), nullable=False, server_default='active'),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.ForeignKeyConstraint(['employee_id'], ['hr_employees.id']),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('idx_hr_certifications_customer', 'hr_certifications', ['customer_id'])
    op.create_index('idx_hr_certifications_employee', 'hr_certifications', ['employee_id'])
    op.create_index('idx_hr_certifications_status', 'hr_certifications', ['status'])
    op.create_index('idx_hr_certifications_expiration', 'hr_certifications', ['expiration_date'])

    # 9. Competency Framework
    op.create_table(
        'hr_competency_framework',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('customer_id', sa.String(length=100), nullable=False),
        sa.Column('competency_name', sa.String(length=255), nullable=False),
        sa.Column('competency_type', sa.String(length=100), nullable=False),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('applicable_positions', sa.JSON(), nullable=True),
        sa.Column('applicable_levels', sa.JSON(), nullable=True),
        sa.Column('proficiency_levels', sa.JSON(), nullable=True),
        sa.Column('is_active', sa.Boolean(), nullable=False, server_default='true'),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('idx_hr_competency_framework_customer', 'hr_competency_framework', ['customer_id'])
    op.create_index('idx_hr_competency_framework_type', 'hr_competency_framework', ['competency_type'])

    # 10. Performance Reviews
    op.create_table(
        'hr_performance_reviews',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('employee_id', sa.Integer(), nullable=False),
        sa.Column('reviewer_id', sa.Integer(), nullable=False),
        sa.Column('customer_id', sa.String(length=100), nullable=False),
        sa.Column('review_period_start', sa.Date(), nullable=False),
        sa.Column('review_period_end', sa.Date(), nullable=False),
        sa.Column('review_type', sa.String(length=50), nullable=False),
        sa.Column('review_cycle', sa.String(length=50), nullable=False),
        sa.Column('overall_rating', sa.Float(), nullable=True),
        sa.Column('overall_summary', sa.Text(), nullable=True),
        sa.Column('promotion_recommended', sa.Boolean(), nullable=False, server_default='false'),
        sa.Column('promotion_readiness', sa.String(length=50), nullable=True),
        sa.Column('technical_competencies', sa.JSON(), nullable=True),
        sa.Column('behavioral_competencies', sa.JSON(), nullable=True),
        sa.Column('leadership_competencies', sa.JSON(), nullable=True),
        sa.Column('previous_goals', sa.JSON(), nullable=True),
        sa.Column('goals_achievement_percentage', sa.Float(), nullable=True),
        sa.Column('new_goals', sa.JSON(), nullable=True),
        sa.Column('okrs', sa.JSON(), nullable=True),
        sa.Column('kpis', sa.JSON(), nullable=True),
        sa.Column('strengths', sa.Text(), nullable=True),
        sa.Column('areas_for_improvement', sa.Text(), nullable=True),
        sa.Column('development_plan', sa.JSON(), nullable=True),
        sa.Column('recommended_training', sa.JSON(), nullable=True),
        sa.Column('peer_feedback', sa.JSON(), nullable=True),
        sa.Column('self_assessment', sa.JSON(), nullable=True),
        sa.Column('manager_comments', sa.Text(), nullable=True),
        sa.Column('status', sa.Enum('draft', 'pending_employee_review', 'pending_manager_approval', 'completed', 'archived', name='reviewstatus'), nullable=False),
        sa.Column('employee_acknowledged_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('manager_approved_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('hr_reviewed_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.ForeignKeyConstraint(['employee_id'], ['hr_employees.id']),
        sa.ForeignKeyConstraint(['reviewer_id'], ['hr_employees.id']),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('idx_hr_performance_reviews_customer', 'hr_performance_reviews', ['customer_id'])
    op.create_index('idx_hr_performance_reviews_employee', 'hr_performance_reviews', ['employee_id'])
    op.create_index('idx_hr_performance_reviews_reviewer', 'hr_performance_reviews', ['reviewer_id'])
    op.create_index('idx_hr_performance_reviews_period', 'hr_performance_reviews', ['review_period_start', 'review_period_end'])
    op.create_index('idx_hr_performance_reviews_status', 'hr_performance_reviews', ['status'])

    # 11. Performance Goals
    op.create_table(
        'hr_performance_goals',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('employee_id', sa.Integer(), nullable=False),
        sa.Column('performance_review_id', sa.Integer(), nullable=True),
        sa.Column('customer_id', sa.String(length=100), nullable=False),
        sa.Column('goal_title', sa.String(length=500), nullable=False),
        sa.Column('goal_description', sa.Text(), nullable=True),
        sa.Column('goal_type', sa.String(length=50), nullable=False),
        sa.Column('category', sa.String(length=50), nullable=False),
        sa.Column('target_completion_date', sa.Date(), nullable=True),
        sa.Column('actual_completion_date', sa.Date(), nullable=True),
        sa.Column('status', sa.String(length=50), nullable=False, server_default='not_started'),
        sa.Column('progress_percentage', sa.Float(), nullable=True, server_default='0.0'),
        sa.Column('success_criteria', sa.JSON(), nullable=True),
        sa.Column('measurement_method', sa.String(length=500), nullable=True),
        sa.Column('weight_percentage', sa.Float(), nullable=True),
        sa.Column('final_rating', sa.Float(), nullable=True),
        sa.Column('notes', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.ForeignKeyConstraint(['employee_id'], ['hr_employees.id']),
        sa.ForeignKeyConstraint(['performance_review_id'], ['hr_performance_reviews.id']),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('idx_hr_performance_goals_customer', 'hr_performance_goals', ['customer_id'])
    op.create_index('idx_hr_performance_goals_employee', 'hr_performance_goals', ['employee_id'])
    op.create_index('idx_hr_performance_goals_review', 'hr_performance_goals', ['performance_review_id'])
    op.create_index('idx_hr_performance_goals_status', 'hr_performance_goals', ['status'])

    # 12. Training Programs
    op.create_table(
        'hr_training_programs',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('customer_id', sa.String(length=100), nullable=False),
        sa.Column('program_name', sa.String(length=255), nullable=False),
        sa.Column('program_code', sa.String(length=50), nullable=False),
        sa.Column('provider', sa.String(length=255), nullable=False),
        sa.Column('category', sa.String(length=100), nullable=False),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('duration_hours', sa.Float(), nullable=True),
        sa.Column('delivery_method', sa.String(length=50), nullable=False),
        sa.Column('cost_per_participant', sa.Numeric(10, 2), nullable=True),
        sa.Column('required_for_positions', sa.JSON(), nullable=True),
        sa.Column('is_mandatory', sa.Boolean(), nullable=False, server_default='false'),
        sa.Column('is_active', sa.Boolean(), nullable=False, server_default='true'),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('idx_hr_training_programs_customer', 'hr_training_programs', ['customer_id'])
    op.create_index('idx_hr_training_programs_category', 'hr_training_programs', ['category'])

    # 13. Employee Training Records
    op.create_table(
        'hr_employee_training_records',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('employee_id', sa.Integer(), nullable=False),
        sa.Column('training_program_id', sa.Integer(), nullable=False),
        sa.Column('customer_id', sa.String(length=100), nullable=False),
        sa.Column('enrollment_date', sa.Date(), nullable=False),
        sa.Column('start_date', sa.Date(), nullable=True),
        sa.Column('completion_date', sa.Date(), nullable=True),
        sa.Column('status', sa.Enum('enrolled', 'in_progress', 'completed', 'failed', 'cancelled', name='trainingstatus'), nullable=False),
        sa.Column('score', sa.Float(), nullable=True),
        sa.Column('certification_earned', sa.Boolean(), nullable=False, server_default='false'),
        sa.Column('certification_id', sa.Integer(), nullable=True),
        sa.Column('instructor_name', sa.String(length=255), nullable=True),
        sa.Column('cost_actual', sa.Numeric(10, 2), nullable=True),
        sa.Column('feedback_rating', sa.Float(), nullable=True),
        sa.Column('feedback_comments', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.ForeignKeyConstraint(['employee_id'], ['hr_employees.id']),
        sa.ForeignKeyConstraint(['training_program_id'], ['hr_training_programs.id']),
        sa.ForeignKeyConstraint(['certification_id'], ['hr_certifications.id']),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('idx_hr_employee_training_records_customer', 'hr_employee_training_records', ['customer_id'])
    op.create_index('idx_hr_employee_training_records_employee', 'hr_employee_training_records', ['employee_id'])
    op.create_index('idx_hr_employee_training_records_program', 'hr_employee_training_records', ['training_program_id'])
    op.create_index('idx_hr_employee_training_records_status', 'hr_employee_training_records', ['status'])

    # 14. Learning Paths
    op.create_table(
        'hr_learning_paths',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('customer_id', sa.String(length=100), nullable=False),
        sa.Column('path_name', sa.String(length=255), nullable=False),
        sa.Column('target_position_id', sa.Integer(), nullable=False),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('estimated_duration_months', sa.Integer(), nullable=True),
        sa.Column('required_training_programs', sa.JSON(), nullable=True),
        sa.Column('required_skills', sa.JSON(), nullable=True),
        sa.Column('is_active', sa.Boolean(), nullable=False, server_default='true'),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.ForeignKeyConstraint(['target_position_id'], ['hr_positions.id']),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('idx_hr_learning_paths_customer', 'hr_learning_paths', ['customer_id'])
    op.create_index('idx_hr_learning_paths_target_position', 'hr_learning_paths', ['target_position_id'])

    # 15. Employee Learning Paths
    op.create_table(
        'hr_employee_learning_paths',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('employee_id', sa.Integer(), nullable=False),
        sa.Column('learning_path_id', sa.Integer(), nullable=False),
        sa.Column('customer_id', sa.String(length=100), nullable=False),
        sa.Column('start_date', sa.Date(), nullable=False),
        sa.Column('target_completion_date', sa.Date(), nullable=True),
        sa.Column('actual_completion_date', sa.Date(), nullable=True),
        sa.Column('progress_percentage', sa.Float(), nullable=True, server_default='0.0'),
        sa.Column('status', sa.String(length=50), nullable=False, server_default='not_started'),
        sa.Column('assigned_by_employee_id', sa.Integer(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.ForeignKeyConstraint(['employee_id'], ['hr_employees.id']),
        sa.ForeignKeyConstraint(['learning_path_id'], ['hr_learning_paths.id']),
        sa.ForeignKeyConstraint(['assigned_by_employee_id'], ['hr_employees.id']),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('idx_hr_employee_learning_paths_customer', 'hr_employee_learning_paths', ['customer_id'])
    op.create_index('idx_hr_employee_learning_paths_employee', 'hr_employee_learning_paths', ['employee_id'])
    op.create_index('idx_hr_employee_learning_paths_path', 'hr_employee_learning_paths', ['learning_path_id'])

    # 16. Time Off Requests
    op.create_table(
        'hr_time_off_requests',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('employee_id', sa.Integer(), nullable=False),
        sa.Column('customer_id', sa.String(length=100), nullable=False),
        sa.Column('request_type', sa.String(length=50), nullable=False),
        sa.Column('start_date', sa.Date(), nullable=False),
        sa.Column('end_date', sa.Date(), nullable=False),
        sa.Column('total_days', sa.Float(), nullable=False),
        sa.Column('status', sa.Enum('pending', 'approved', 'denied', 'cancelled', name='timeoffstatus'), nullable=False),
        sa.Column('approved_by_employee_id', sa.Integer(), nullable=True),
        sa.Column('approved_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('notes', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.ForeignKeyConstraint(['employee_id'], ['hr_employees.id']),
        sa.ForeignKeyConstraint(['approved_by_employee_id'], ['hr_employees.id']),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('idx_hr_time_off_requests_customer', 'hr_time_off_requests', ['customer_id'])
    op.create_index('idx_hr_time_off_requests_employee', 'hr_time_off_requests', ['employee_id'])
    op.create_index('idx_hr_time_off_requests_dates', 'hr_time_off_requests', ['start_date', 'end_date'])
    op.create_index('idx_hr_time_off_requests_status', 'hr_time_off_requests', ['status'])

    # 17. Emergency Contacts
    op.create_table(
        'hr_emergency_contacts',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('employee_id', sa.Integer(), nullable=False),
        sa.Column('customer_id', sa.String(length=100), nullable=False),
        sa.Column('contact_name', sa.String(length=255), nullable=False),
        sa.Column('relationship_type', sa.String(length=100), nullable=False),
        sa.Column('phone_primary', sa.String(length=50), nullable=False),
        sa.Column('phone_secondary', sa.String(length=50), nullable=True),
        sa.Column('email', sa.String(length=255), nullable=True),
        sa.Column('address', sa.JSON(), nullable=True),
        sa.Column('is_primary_contact', sa.Boolean(), nullable=False, server_default='false'),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.ForeignKeyConstraint(['employee_id'], ['hr_employees.id']),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('idx_hr_emergency_contacts_customer', 'hr_emergency_contacts', ['customer_id'])
    op.create_index('idx_hr_emergency_contacts_employee', 'hr_emergency_contacts', ['employee_id'])

    # 18-20. Data Pipeline Support Tables
    op.create_table(
        'hr_data_field_mappings',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('customer_id', sa.String(length=100), nullable=False),
        sa.Column('source_system', sa.String(length=100), nullable=False),
        sa.Column('source_field_name', sa.String(length=255), nullable=False),
        sa.Column('target_table', sa.String(length=100), nullable=False),
        sa.Column('target_field_name', sa.String(length=100), nullable=False),
        sa.Column('transformation_rule', sa.JSON(), nullable=True),
        sa.Column('is_required', sa.Boolean(), nullable=False, server_default='false'),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('idx_hr_data_field_mappings_customer', 'hr_data_field_mappings', ['customer_id'])
    op.create_index('idx_hr_data_field_mappings_source', 'hr_data_field_mappings', ['source_system'])

    op.create_table(
        'hr_data_ingestion_logs',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('customer_id', sa.String(length=100), nullable=False),
        sa.Column('ingestion_batch_id', sa.String(length=100), nullable=False),
        sa.Column('source_system', sa.String(length=100), nullable=False),
        sa.Column('records_processed', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('records_succeeded', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('records_failed', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('errors', sa.JSON(), nullable=True),
        sa.Column('started_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('completed_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('idx_hr_data_ingestion_logs_customer', 'hr_data_ingestion_logs', ['customer_id'])
    op.create_index('idx_hr_data_ingestion_logs_batch', 'hr_data_ingestion_logs', ['ingestion_batch_id'])
    op.create_index('idx_hr_data_ingestion_logs_started', 'hr_data_ingestion_logs', ['started_at'])

    op.create_table(
        'hr_data_validation_rules',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('customer_id', sa.String(length=100), nullable=False),
        sa.Column('rule_name', sa.String(length=255), nullable=False),
        sa.Column('target_table', sa.String(length=100), nullable=False),
        sa.Column('target_field', sa.String(length=100), nullable=False),
        sa.Column('validation_type', sa.String(length=50), nullable=False),
        sa.Column('validation_config', sa.JSON(), nullable=False),
        sa.Column('error_message', sa.String(length=500), nullable=False),
        sa.Column('is_active', sa.Boolean(), nullable=False, server_default='true'),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('idx_hr_data_validation_rules_customer', 'hr_data_validation_rules', ['customer_id'])
    op.create_index('idx_hr_data_validation_rules_table', 'hr_data_validation_rules', ['target_table'])


def downgrade() -> None:
    """Drop HR schema tables."""
    # Drop tables in reverse order to handle foreign key dependencies
    op.drop_table('hr_data_validation_rules')
    op.drop_table('hr_data_ingestion_logs')
    op.drop_table('hr_data_field_mappings')
    op.drop_table('hr_emergency_contacts')
    op.drop_table('hr_time_off_requests')
    op.drop_table('hr_employee_learning_paths')
    op.drop_table('hr_learning_paths')
    op.drop_table('hr_employee_training_records')
    op.drop_table('hr_training_programs')
    op.drop_table('hr_performance_goals')
    op.drop_table('hr_performance_reviews')
    op.drop_table('hr_competency_framework')
    op.drop_table('hr_certifications')
    op.drop_table('hr_employee_skills')
    op.drop_table('hr_skills')
    op.drop_table('hr_compensation')
    op.drop_table('hr_employment_history')
    op.drop_table('hr_employees')
    op.drop_table('hr_positions')
    op.drop_table('hr_departments')

    # Drop enum types
    op.execute("""
        DROP TYPE IF EXISTS timeoffstatus;
        DROP TYPE IF EXISTS reviewstatus;
        DROP TYPE IF EXISTS trainingstatus;
        DROP TYPE IF EXISTS proficiencylevel;
        DROP TYPE IF EXISTS changetype;
        DROP TYPE IF EXISTS worklocation;
        DROP TYPE IF EXISTS employmenttype;
        DROP TYPE IF EXISTS employmentstatus;
    """)

