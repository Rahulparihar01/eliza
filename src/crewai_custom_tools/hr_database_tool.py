"""
Custom CrewAI Tool for HR Database Queries

Provides CrewAI agents with access to HR data from PostgreSQL database.
"""
from typing import Any, Optional, Dict
from crewai.tools import BaseTool
from pydantic import Field

from src.core.logging import get_logger, LogCategory

logger = get_logger(__name__, component="crewai.tools")


class HRDatabaseTool(BaseTool):
    """
    CrewAI tool for querying HR database.
    
    Provides access to:
    - Employee information (skills, roles, departments)
    - Department structure and hierarchy
    - Performance metrics
    - Training and development records
    """
    
    name: str = "HR Database Query"
    description: str = """
    Query the HR database to retrieve employee, department, skills, performance, 
    and training data. 
    
    Input format: JSON string with keys:
    - query_type: "employees" | "departments" | "skills" | "performance" | "training"
    - filters: Dict of filters (e.g., {"department": "Engineering", "role": "Senior Engineer"})
    - limit: Max number of results (default: 10)
    
    Example: '{"query_type": "employees", "filters": {"department": "Engineering"}, "limit": 5}'
    
    Returns: JSON string with query results.
    """
    
    customer_id: str = Field(description="Customer ID for data isolation")
    
    def _run(self, query_params: str) -> str:
        """
        Execute HR database query.
        
        Args:
            query_params: JSON string with query parameters
            
        Returns:
            JSON string with query results
        """
        import json
        
        try:
            # Parse query parameters
            params = json.loads(query_params) if isinstance(query_params, str) else query_params
            query_type = params.get("query_type", "employees")
            filters = params.get("filters", {})
            limit = params.get("limit", 10)
            
            logger.info(
                "hr_database_tool_query",
                category=LogCategory.BUSINESS,
                metadata={
                    "query_type": query_type,
                    "customer_id": self.customer_id,
                    "limit": limit,
                    "filters": filters
                }
            )
            
            # Route to appropriate query method - get SessionLocal and initialize if needed
            from src import models
            from src.models.database import init_database
            SessionLocal = getattr(models, 'SessionLocal')
            
            # Self-initialize if not already done (happens in standalone scripts)
            if SessionLocal is None:
                logger.info("SessionLocal not initialized, calling init_database()")
                init_database()
                SessionLocal = getattr(models, 'SessionLocal')
            
            if SessionLocal is None:
                raise RuntimeError("SessionLocal is still None after init_database() - check database configuration")
            
            db = SessionLocal()
            try:
                if query_type == "employees":
                    results = self._query_employees(db, filters, limit)
                elif query_type == "departments":
                    results = self._query_departments(db, filters, limit)
                elif query_type == "skills":
                    results = self._query_skills(db, filters, limit)
                elif query_type == "performance":
                    results = self._query_performance(db, filters, limit)
                elif query_type == "training":
                    results = self._query_training(db, filters, limit)
                else:
                    results = {"error": f"Unknown query_type: {query_type}"}
                
                logger.info(
                    "hr_database_tool_query_complete",
                    category=LogCategory.BUSINESS,
                    metadata={
                        "query_type": query_type,
                        "results_count": len(results.get("data", [])) if "data" in results else 0
                    }
                )
                
                return json.dumps(results, default=str)
            finally:
                db.close()
                
        except Exception as e:
            logger.error(
                "hr_database_tool_error",
                exception=e,
                category=LogCategory.BUSINESS,
                metadata={"query_params": str(query_params)}
            )
            return json.dumps({
                "error": str(e),
                "query_params": query_params
            })
    
    def _query_employees(self, db, filters: Dict, limit: int) -> Dict[str, Any]:
        """Query employee data"""
        from src.models.hr import Employee, Department
        
        query = db.query(Employee).filter(Employee.customer_id == self.customer_id)
        
        # Apply filters
        if "department" in filters:
            # Join with Department table to filter by department name
            query = query.join(Department, Employee.department_id == Department.id)
            query = query.filter(Department.name.ilike(f"%{filters['department']}%"))
        if "employment_status" in filters:
            query = query.filter(Employee.employment_status == filters["employment_status"])
        
        employees = query.limit(limit).all()
        
        return {
            "query_type": "employees",
            "count": len(employees),
            "data": [
                {
                    "id": emp.id,
                    "full_name": emp.full_name,
                    "email": emp.email,
                    "department": emp.department.name if emp.department else None,
                    "department_id": emp.department_id,
                    "employment_status": str(emp.employment_status.value) if emp.employment_status else None,
                    "employment_type": str(emp.employment_type.value) if emp.employment_type else None,
                    "hire_date": emp.hire_date,
                    "manager_id": emp.manager_id
                }
                for emp in employees
            ]
        }
    
    def _query_departments(self, db, filters: Dict, limit: int) -> Dict[str, Any]:
        """Query department data"""
        from src.models.hr import Department
        
        query = db.query(Department).filter(Department.customer_id == self.customer_id)
        
        if "name" in filters:
            query = query.filter(Department.name.ilike(f"%{filters['name']}%"))
        
        departments = query.limit(limit).all()
        
        return {
            "query_type": "departments",
            "count": len(departments),
            "data": [
                {
                    "id": dept.id,
                    "name": dept.name,
                    "description": dept.description,
                    "head_employee_id": dept.head_employee_id,
                    "parent_department_id": dept.parent_department_id
                }
                for dept in departments
            ]
        }
    
    def _query_skills(self, db, filters: Dict, limit: int) -> Dict[str, Any]:
        """Query employee skills data"""
        from src.models.hr import EmployeeSkill, Skill
        
        query = db.query(EmployeeSkill, Skill).join(Skill).filter(
            EmployeeSkill.customer_id == self.customer_id
        )
        
        if "skill_name" in filters:
            query = query.filter(Skill.name.ilike(f"%{filters['skill_name']}%"))
        if "proficiency_level" in filters:
            query = query.filter(EmployeeSkill.proficiency_level == filters["proficiency_level"])
        
        results = query.limit(limit).all()
        
        return {
            "query_type": "skills",
            "count": len(results),
            "data": [
                {
                    "employee_id": emp_skill.employee_id,
                    "skill_name": skill.name,
                    "category": skill.category,
                    "proficiency_level": emp_skill.proficiency_level,
                    "years_of_experience": emp_skill.years_of_experience
                }
                for emp_skill, skill in results
            ]
        }
    
    def _query_performance(self, db, filters: Dict, limit: int) -> Dict[str, Any]:
        """Query performance review data"""
        from src.models.hr import PerformanceReview
        
        query = db.query(PerformanceReview).filter(
            PerformanceReview.customer_id == self.customer_id
        )
        
        if "employee_id" in filters:
            query = query.filter(PerformanceReview.employee_id == filters["employee_id"])
        if "rating" in filters:
            query = query.filter(PerformanceReview.overall_rating >= filters["rating"])
        
        reviews = query.order_by(PerformanceReview.review_period_end.desc()).limit(limit).all()
        
        return {
            "query_type": "performance",
            "count": len(reviews),
            "data": [
                {
                    "id": review.id,
                    "employee_id": review.employee_id,
                    "review_period_start": review.review_period_start,
                    "review_period_end": review.review_period_end,
                    "overall_rating": review.overall_rating,
                    "reviewer_id": review.reviewer_id,
                    "strengths": review.strengths,
                    "areas_for_improvement": review.areas_for_improvement
                }
                for review in reviews
            ]
        }
    
    def _query_training(self, db, filters: Dict, limit: int) -> Dict[str, Any]:
        """Query training records"""
        from src.models.hr import TrainingRecord
        
        query = db.query(TrainingRecord).filter(
            TrainingRecord.customer_id == self.customer_id
        )
        
        if "employee_id" in filters:
            query = query.filter(TrainingRecord.employee_id == filters["employee_id"])
        if "status" in filters:
            query = query.filter(TrainingRecord.status == filters["status"])
        
        records = query.order_by(TrainingRecord.completion_date.desc()).limit(limit).all()
        
        return {
            "query_type": "training",
            "count": len(records),
            "data": [
                {
                    "id": record.id,
                    "employee_id": record.employee_id,
                    "training_name": record.training_name,
                    "training_type": record.training_type,
                    "status": record.status,
                    "completion_date": record.completion_date,
                    "credits_earned": record.credits_earned
                }
                for record in records
            ]
        }
