"""Add HR summary views for executive insights

Revision ID: 013_add_hr_summary_views
Revises: a0c1ff521188
Create Date: 2025-10-01 17:30:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '013_add_hr_summary_views'
down_revision = 'a0c1ff521188'
branch_labels = None
depends_on = None
tags = ["core"]


def upgrade() -> None:
    """Create HR summary views for executive insights."""
    
    # ========================================================================
    # View 1: Employee Overview Summary
    # ========================================================================
    op.execute("""
        CREATE OR REPLACE VIEW hr_employee_overview_summary AS
        SELECT 
            e.customer_id,
            COUNT(DISTINCT e.id) as total_employees,
            COUNT(DISTINCT CASE WHEN e.employment_status = 'active' THEN e.id END) as active_employees,
            COUNT(DISTINCT CASE WHEN e.employment_status = 'on_leave' THEN e.id END) as on_leave_employees,
            COUNT(DISTINCT CASE WHEN e.employment_status = 'terminated' THEN e.id END) as terminated_employees,
            COUNT(DISTINCT CASE WHEN e.employment_type = 'full_time' THEN e.id END) as full_time_employees,
            COUNT(DISTINCT CASE WHEN e.employment_type = 'part_time' THEN e.id END) as part_time_employees,
            COUNT(DISTINCT CASE WHEN e.employment_type = 'contractor' THEN e.id END) as contractor_employees,
            COUNT(DISTINCT CASE WHEN e.work_location = 'office' THEN e.id END) as office_employees,
            COUNT(DISTINCT CASE WHEN e.work_location = 'remote' THEN e.id END) as remote_employees,
            COUNT(DISTINCT CASE WHEN e.work_location = 'hybrid' THEN e.id END) as hybrid_employees,
            COUNT(DISTINCT d.id) as total_departments,
            COUNT(DISTINCT p.id) as total_positions,
            AVG(EXTRACT(YEAR FROM AGE(CURRENT_DATE, e.hire_date))) as avg_tenure_years,
            json_agg(DISTINCT jsonb_build_object(
                'department_id', d.id,
                'department_name', d.name,
                'employee_count', (
                    SELECT COUNT(*) 
                    FROM hr_employees e2 
                    WHERE e2.department_id = d.id 
                    AND e2.customer_id = e.customer_id
                    AND e2.employment_status = 'active'
                )
            )) FILTER (WHERE d.id IS NOT NULL) as department_breakdown,
            json_agg(DISTINCT jsonb_build_object(
                'position_id', p.id,
                'position_title', p.title,
                'position_level', p.level,
                'employee_count', (
                    SELECT COUNT(*) 
                    FROM hr_employees e3 
                    WHERE e3.position_id = p.id 
                    AND e3.customer_id = e.customer_id
                    AND e3.employment_status = 'active'
                )
            )) FILTER (WHERE p.id IS NOT NULL) as position_breakdown
        FROM hr_employees e
        LEFT JOIN hr_departments d ON e.department_id = d.id AND d.customer_id = e.customer_id
        LEFT JOIN hr_positions p ON e.position_id = p.id AND p.customer_id = e.customer_id
        GROUP BY e.customer_id
    """)
    
    # ========================================================================
    # View 2: Skills & Competencies Summary
    # ========================================================================
    op.execute("""
        CREATE OR REPLACE VIEW hr_skills_competencies_summary AS
        SELECT 
            e.customer_id,
            COUNT(DISTINCT s.id) as total_skills,
            COUNT(DISTINCT es.id) as total_skill_assignments,
            COUNT(DISTINCT es.employee_id) as employees_with_skills,
            COUNT(DISTINCT CASE WHEN es.proficiency_level = 'expert' THEN es.id END) as expert_level_skills,
            COUNT(DISTINCT CASE WHEN es.proficiency_level = 'advanced' THEN es.id END) as advanced_level_skills,
            COUNT(DISTINCT CASE WHEN es.proficiency_level = 'intermediate' THEN es.id END) as intermediate_level_skills,
            COUNT(DISTINCT CASE WHEN es.proficiency_level = 'beginner' THEN es.id END) as beginner_level_skills,
            AVG(es.years_experience) FILTER (WHERE es.years_experience IS NOT NULL) as avg_years_experience,
            json_agg(DISTINCT jsonb_build_object(
                'skill_id', s.id,
                'skill_name', s.name,
                'skill_category', s.category,
                'employee_count', (
                    SELECT COUNT(DISTINCT es2.employee_id)
                    FROM hr_employee_skills es2
                    WHERE es2.skill_id = s.id
                    AND es2.customer_id = e.customer_id
                ),
                'avg_proficiency', (
                    SELECT AVG(
                        CASE es2.proficiency_level
                            WHEN 'beginner' THEN 1
                            WHEN 'intermediate' THEN 2
                            WHEN 'advanced' THEN 3
                            WHEN 'expert' THEN 4
                        END
                    )
                    FROM hr_employee_skills es2
                    WHERE es2.skill_id = s.id
                    AND es2.customer_id = e.customer_id
                )
            )) FILTER (WHERE s.id IS NOT NULL) as skill_breakdown,
            json_agg(DISTINCT jsonb_build_object(
                'category', s.category,
                'skill_count', (
                    SELECT COUNT(DISTINCT s2.id)
                    FROM hr_skills s2
                    WHERE s2.category = s.category
                    AND s2.customer_id = e.customer_id
                ),
                'employee_count', (
                    SELECT COUNT(DISTINCT es2.employee_id)
                    FROM hr_employee_skills es2
                    JOIN hr_skills s2 ON es2.skill_id = s2.id
                    WHERE s2.category = s.category
                    AND es2.customer_id = e.customer_id
                )
            )) FILTER (WHERE s.category IS NOT NULL) as category_breakdown
        FROM hr_employees e
        LEFT JOIN hr_employee_skills es ON e.id = es.employee_id AND es.customer_id = e.customer_id
        LEFT JOIN hr_skills s ON es.skill_id = s.id AND s.customer_id = e.customer_id
        WHERE e.employment_status = 'active'
        GROUP BY e.customer_id
    """)
    
    # ========================================================================
    # View 3: Performance & Development Summary
    # ========================================================================
    op.execute("""
        CREATE OR REPLACE VIEW hr_performance_development_summary AS
        SELECT 
            e.customer_id,
            COUNT(DISTINCT e.id) as total_active_employees,
            COUNT(DISTINCT pr.id) as total_performance_reviews,
            COUNT(DISTINCT CASE WHEN pr.review_period_end >= CURRENT_DATE - INTERVAL '12 months' THEN pr.id END) as reviews_last_12_months,
            AVG(pr.overall_rating) FILTER (WHERE pr.overall_rating IS NOT NULL) as avg_overall_rating,
            COUNT(DISTINCT CASE WHEN pr.promotion_readiness = 'ready_now' THEN pr.employee_id END) as ready_for_promotion,
            COUNT(DISTINCT CASE WHEN pr.promotion_readiness = 'ready_6_months' THEN pr.employee_id END) as ready_in_6_months,
            COUNT(DISTINCT CASE WHEN pr.promotion_readiness = 'ready_12_months' THEN pr.employee_id END) as ready_in_12_months,
            COUNT(DISTINCT etr.id) as total_training_records,
            COUNT(DISTINCT CASE WHEN etr.status = 'completed' THEN etr.id END) as completed_trainings,
            COUNT(DISTINCT CASE WHEN etr.status = 'in_progress' THEN etr.id END) as in_progress_trainings,
            COUNT(DISTINCT CASE WHEN etr.status = 'enrolled' THEN etr.id END) as enrolled_trainings,
            AVG(etr.feedback_rating) FILTER (WHERE etr.feedback_rating IS NOT NULL) as avg_training_rating,
            AVG(pr.goals_achievement_percentage) FILTER (WHERE pr.goals_achievement_percentage IS NOT NULL) as avg_goals_achievement,
            json_agg(DISTINCT jsonb_build_object(
                'department_id', d.id,
                'department_name', d.name,
                'avg_rating', (
                    SELECT AVG(pr2.overall_rating)
                    FROM hr_performance_reviews pr2
                    JOIN hr_employees e2 ON pr2.employee_id = e2.id
                    WHERE e2.department_id = d.id
                    AND e2.customer_id = e.customer_id
                    AND pr2.overall_rating IS NOT NULL
                ),
                'promotion_ready_count', (
                    SELECT COUNT(DISTINCT pr2.employee_id)
                    FROM hr_performance_reviews pr2
                    JOIN hr_employees e2 ON pr2.employee_id = e2.id
                    WHERE e2.department_id = d.id
                    AND e2.customer_id = e.customer_id
                    AND pr2.promotion_readiness IN ('ready_now', 'ready_6_months')
                )
            )) FILTER (WHERE d.id IS NOT NULL) as department_performance,
            json_agg(DISTINCT jsonb_build_object(
                'training_program_id', tp.id,
                'program_name', tp.program_name,
                'completion_count', (
                    SELECT COUNT(*)
                    FROM hr_employee_training_records etr2
                    WHERE etr2.training_program_id = tp.id
                    AND etr2.customer_id = e.customer_id
                    AND etr2.status = 'completed'
                ),
                'avg_rating', (
                    SELECT AVG(etr2.feedback_rating)
                    FROM hr_employee_training_records etr2
                    WHERE etr2.training_program_id = tp.id
                    AND etr2.customer_id = e.customer_id
                    AND etr2.feedback_rating IS NOT NULL
                )
            )) FILTER (WHERE tp.id IS NOT NULL) as training_program_stats
        FROM hr_employees e
        LEFT JOIN hr_performance_reviews pr ON e.id = pr.employee_id AND pr.customer_id = e.customer_id
        LEFT JOIN hr_employee_training_records etr ON e.id = etr.employee_id AND etr.customer_id = e.customer_id
        LEFT JOIN hr_training_programs tp ON etr.training_program_id = tp.id AND tp.customer_id = e.customer_id
        LEFT JOIN hr_departments d ON e.department_id = d.id AND d.customer_id = e.customer_id
        WHERE e.employment_status = 'active'
        GROUP BY e.customer_id
    """)


def downgrade() -> None:
    """Drop HR summary views."""
    op.execute("DROP VIEW IF EXISTS hr_performance_development_summary")
    op.execute("DROP VIEW IF EXISTS hr_skills_competencies_summary")
    op.execute("DROP VIEW IF EXISTS hr_employee_overview_summary")

