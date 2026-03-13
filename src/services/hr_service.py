"""
HR Service Layer

This module provides service layer operations for HR data management,
following the Feature Development Guide patterns with structured logging,
async operations, and proper error handling.
"""

from typing import List, Optional
from sqlalchemy import select, and_, or_, func, desc
from sqlalchemy.orm import joinedload, selectinload
import sqlalchemy as sa

from src.services.base_service import AsyncBaseService
from src.core.logging import get_logger, bind_context, reset_context, LogCategory
from src.models.hr import (
    Department,
    Position,
    Employee,
    Skill,
    EmployeeSkill,
    PerformanceReview,
    TrainingProgram,
    EmployeeTrainingRecord,
)

logger = get_logger(__name__, component="hr.service")


class HRService(AsyncBaseService):
    """Service for HR data management operations"""

    # ========================================================================
    # Summary Views Operations
    # ========================================================================

    async def get_employee_overview_summary(self, customer_id: str) -> Optional[dict]:
        """
        Get employee overview summary for executives.

        Args:
            customer_id: Customer ID for multi-tenancy

        Returns:
            Dictionary with employee overview metrics
        """
        context_tokens = bind_context(customer_id=customer_id)

        try:
            async def operation(session):
                result = await session.execute(
                    select(sa.text("*")).select_from(sa.text("hr_employee_overview_summary")).where(
                        sa.text("customer_id = :customer_id")
                    ),
                    {"customer_id": customer_id}
                )
                row = result.first()
                if row:
                    return dict(row._mapping)
                return None

            return await self.execute_with_session(operation)

        except Exception as e:
            logger.error(
                "Failed to get employee overview summary",
                exception=e,
                category=LogCategory.DATA_PROCESSING,
                metadata={'customer_id': customer_id}
            )
            raise
        finally:
            reset_context(context_tokens)

    async def get_skills_competencies_summary(self, customer_id: str) -> Optional[dict]:
        """
        Get skills and competencies summary for executives.

        Args:
            customer_id: Customer ID for multi-tenancy

        Returns:
            Dictionary with skills and competencies metrics
        """
        context_tokens = bind_context(customer_id=customer_id)

        try:
            async def operation(session):
                result = await session.execute(
                    select(sa.text("*")).select_from(sa.text("hr_skills_competencies_summary")).where(
                        sa.text("customer_id = :customer_id")
                    ),
                    {"customer_id": customer_id}
                )
                row = result.first()
                if row:
                    return dict(row._mapping)
                return None

            return await self.execute_with_session(operation)

        except Exception as e:
            logger.error(
                "Failed to get skills competencies summary",
                exception=e,
                category=LogCategory.DATA_PROCESSING,
                metadata={'customer_id': customer_id}
            )
            raise
        finally:
            reset_context(context_tokens)

    async def get_performance_development_summary(self, customer_id: str) -> Optional[dict]:
        """
        Get performance and development summary for executives.

        Args:
            customer_id: Customer ID for multi-tenancy

        Returns:
            Dictionary with performance and development metrics
        """
        context_tokens = bind_context(customer_id=customer_id)

        try:
            async def operation(session):
                result = await session.execute(
                    select(sa.text("*")).select_from(sa.text("hr_performance_development_summary")).where(
                        sa.text("customer_id = :customer_id")
                    ),
                    {"customer_id": customer_id}
                )
                row = result.first()
                if row:
                    return dict(row._mapping)
                return None

            return await self.execute_with_session(operation)

        except Exception as e:
            logger.error(
                "Failed to get performance development summary",
                exception=e,
                category=LogCategory.DATA_PROCESSING,
                metadata={'customer_id': customer_id}
            )
            raise
        finally:
            reset_context(context_tokens)

    async def get_hr_tables_list(self, customer_id: str) -> List[dict]:
        """
        Get list of all HR tables with metadata.

        Args:
            customer_id: Customer ID for multi-tenancy

        Returns:
            List of dictionaries with table information
        """
        context_tokens = bind_context(customer_id=customer_id)

        try:
            tables_info = [
                {
                    "table_name": "hr_employees",
                    "display_name": "Employees",
                    "description": "Employee records with personal and employment information",
                    "endpoint": "/v1/hr/employees"
                },
                {
                    "table_name": "hr_departments",
                    "display_name": "Departments",
                    "description": "Organizational departments and hierarchy",
                    "endpoint": "/v1/hr/departments"
                },
                {
                    "table_name": "hr_positions",
                    "display_name": "Positions",
                    "description": "Job positions and levels",
                    "endpoint": "/v1/hr/positions"
                },
                {
                    "table_name": "hr_skills",
                    "display_name": "Skills",
                    "description": "Available skills and competencies",
                    "endpoint": "/v1/hr/skills"
                },
                {
                    "table_name": "hr_employee_skills",
                    "display_name": "Employee Skills",
                    "description": "Employee skill assignments and proficiency levels",
                    "endpoint": "/v1/hr/employee-skills"
                },
                {
                    "table_name": "hr_performance_reviews",
                    "display_name": "Performance Reviews",
                    "description": "Employee performance reviews and ratings",
                    "endpoint": "/v1/hr/performance-reviews"
                },
                {
                    "table_name": "hr_training_programs",
                    "display_name": "Training Programs",
                    "description": "Available training programs",
                    "endpoint": "/v1/hr/training-programs"
                },
                {
                    "table_name": "hr_employee_training_records",
                    "display_name": "Training Records",
                    "description": "Employee training completion records",
                    "endpoint": "/v1/hr/training-records"
                },
            ]

            # Get record counts for each table
            async def operation(session):
                for table_info in tables_info:
                    table_name = table_info["table_name"]
                    result = await session.execute(
                        sa.text(f"SELECT COUNT(*) as count FROM {table_name} WHERE customer_id = :customer_id"),
                        {"customer_id": customer_id}
                    )
                    row = result.first()
                    table_info["record_count"] = row[0] if row else 0

                return tables_info

            return await self.execute_with_session(operation)

        except Exception as e:
            logger.error(
                "Failed to get HR tables list",
                exception=e,
                category=LogCategory.DATA_PROCESSING,
                metadata={'customer_id': customer_id}
            )
            raise
        finally:
            reset_context(context_tokens)

    async def get_hr_table_data(
        self,
        table_name: str,
        customer_id: str,
        limit: int = 100,
        offset: int = 0
    ) -> dict:
        """
        Get data from a specific HR table with pagination.

        Args:
            table_name: Name of the HR table
            customer_id: Customer ID for multi-tenancy
            limit: Maximum number of rows to return
            offset: Number of rows to skip

        Returns:
            Dictionary with data, total_count, columns, limit, and offset

        Raises:
            ValueError: If table_name is not a valid HR table
        """
        # Whitelist of allowed HR tables for security
        allowed_tables = {
            "hr_employees",
            "hr_departments",
            "hr_positions",
            "hr_skills",
            "hr_employee_skills",
            "hr_performance_reviews",
            "hr_training_programs",
            "hr_employee_training_records",
        }

        if table_name not in allowed_tables:
            raise ValueError(f"Invalid table name: {table_name}")

        context_tokens = bind_context(customer_id=customer_id, table_name=table_name)

        try:
            async def operation(session):
                # Get total count
                count_result = await session.execute(
                    sa.text(f"SELECT COUNT(*) FROM {table_name} WHERE customer_id = :customer_id"),
                    {"customer_id": customer_id}
                )
                total_count = count_result.scalar()

                # Get column names
                columns_result = await session.execute(
                    sa.text(f"""
                        SELECT column_name
                        FROM information_schema.columns
                        WHERE table_name = :table_name
                        AND table_schema = 'public'
                        ORDER BY ordinal_position
                    """),
                    {"table_name": table_name}
                )
                columns = [row[0] for row in columns_result.fetchall()]

                # Get data with pagination
                data_result = await session.execute(
                    sa.text(f"""
                        SELECT * FROM {table_name}
                        WHERE customer_id = :customer_id
                        ORDER BY id
                        LIMIT :limit OFFSET :offset
                    """),
                    {"customer_id": customer_id, "limit": limit, "offset": offset}
                )

                # Convert rows to dictionaries
                rows = data_result.fetchall()
                data = []
                for row in rows:
                    row_dict = {}
                    for i, col in enumerate(columns):
                        value = row[i]
                        # Convert datetime objects to ISO format strings
                        if hasattr(value, 'isoformat'):
                            value = value.isoformat()
                        # Convert UUID objects to strings
                        elif hasattr(value, 'hex'):
                            value = str(value)
                        row_dict[col] = value
                    data.append(row_dict)

                return {
                    "data": data,
                    "total_count": total_count,
                    "columns": columns,
                    "limit": limit,
                    "offset": offset,
                    "table_name": table_name
                }

            return await self.execute_with_session(operation)

        except ValueError:
            # Re-raise ValueError for invalid table names
            raise
        except Exception as e:
            logger.error(
                f"Failed to get data from table {table_name}",
                exception=e,
                category=LogCategory.DATA_PROCESSING,
                metadata={'customer_id': customer_id, 'table_name': table_name}
            )
            raise
        finally:
            reset_context(context_tokens)

    # ========================================================================
    # Department Operations
    # ========================================================================
    
    async def list_departments(
        self,
        customer_id: str,
        search: Optional[str] = None,
        limit: int = 20,
        offset: int = 0
    ) -> List[Department]:
        """
        Get paginated list of departments with optional filtering.
        
        Args:
            customer_id: Customer ID for multi-tenancy
            search: Optional search term for department name or code
            limit: Maximum number of results
            offset: Pagination offset
            
        Returns:
            List of Department objects
        """
        context_tokens = bind_context(customer_id=customer_id)
        
        try:
            op_id = logger.start_operation(
                "list_departments",
                category=LogCategory.DATA_RETRIEVAL,
                user_message=f"Retrieving departments for customer {customer_id}",
                metadata={'search': search, 'limit': limit, 'offset': offset}
            )
            
            async def operation(session):
                query = select(Department).where(Department.customer_id == customer_id)
                
                if search:
                    search_term = f"%{search}%"
                    query = query.where(
                        or_(
                            Department.name.ilike(search_term),
                            Department.code.ilike(search_term)
                        )
                    )
                
                query = query.order_by(Department.name).limit(limit).offset(offset)
                result = await session.execute(query)
                return list(result.scalars().all())
            
            departments = await self.execute_with_session(operation)
            
            logger.end_operation(
                op_id,
                success=True,
                items_processed=len(departments),
                user_message=f"Retrieved {len(departments)} departments"
            )
            
            return departments
            
        except Exception as e:
            logger.error(
                f"Failed to list departments",
                exception=e,
                category=LogCategory.DATA_RETRIEVAL,
                metadata={'customer_id': customer_id}
            )
            if 'op_id' in locals():
                logger.end_operation(op_id, success=False, error=str(e))
            raise
        finally:
            reset_context(context_tokens)
    
    async def get_department(self, department_id: int, customer_id: str) -> Optional[Department]:
        """
        Get a single department by ID.
        
        Args:
            department_id: Department ID
            customer_id: Customer ID for multi-tenancy
            
        Returns:
            Department object or None if not found
        """
        context_tokens = bind_context(customer_id=customer_id, department_id=str(department_id))
        
        try:
            async def operation(session):
                query = select(Department).where(
                    and_(
                        Department.id == department_id,
                        Department.customer_id == customer_id
                    )
                )
                result = await session.execute(query)
                return result.scalar_one_or_none()
            
            return await self.execute_with_session(operation)
            
        except Exception as e:
            logger.error(
                f"Failed to get department {department_id}",
                exception=e,
                category=LogCategory.DATA_RETRIEVAL,
                metadata={'department_id': department_id, 'customer_id': customer_id}
            )
            raise
        finally:
            reset_context(context_tokens)
    
    async def create_department(self, department: Department) -> Department:
        """
        Create a new department.
        
        Args:
            department: Department object to create
            
        Returns:
            Created Department object with ID
        """
        context_tokens = bind_context(customer_id=department.customer_id)
        
        try:
            op_id = logger.start_operation(
                "create_department",
                category=LogCategory.DATA_MODIFICATION,
                user_message=f"Creating department {department.name}",
                metadata={'department_name': department.name, 'department_code': department.code}
            )
            
            async def operation(session):
                session.add(department)
                await session.flush()
                await session.refresh(department)
                return department
            
            created_dept = await self.execute_with_session(operation)
            
            logger.end_operation(
                op_id,
                success=True,
                items_processed=1,
                user_message=f"Department {created_dept.name} created successfully"
            )
            
            return created_dept
            
        except Exception as e:
            logger.error(
                f"Failed to create department",
                exception=e,
                category=LogCategory.DATA_MODIFICATION,
                metadata={'department_name': department.name}
            )
            if 'op_id' in locals():
                logger.end_operation(op_id, success=False, error=str(e))
            raise
        finally:
            reset_context(context_tokens)
    
    async def count_departments(
        self,
        customer_id: str,
        search: Optional[str] = None
    ) -> int:
        """
        Count departments with optional filtering.
        
        Args:
            customer_id: Customer ID for multi-tenancy
            search: Optional search term
            
        Returns:
            Total count of departments
        """
        try:
            async def operation(session):
                query = select(func.count(Department.id)).where(Department.customer_id == customer_id)
                
                if search:
                    search_term = f"%{search}%"
                    query = query.where(
                        or_(
                            Department.name.ilike(search_term),
                            Department.code.ilike(search_term)
                        )
                    )
                
                result = await session.execute(query)
                return result.scalar()
            
            return await self.execute_with_session(operation)
            
        except Exception as e:
            logger.error(
                f"Failed to count departments",
                exception=e,
                category=LogCategory.DATA_RETRIEVAL,
                metadata={'customer_id': customer_id}
            )
            raise
    
    # ========================================================================
    # Employee Operations
    # ========================================================================
    
    async def list_employees(
        self,
        customer_id: str,
        search: Optional[str] = None,
        department_id: Optional[int] = None,
        employment_status: Optional[str] = None,
        limit: int = 20,
        offset: int = 0
    ) -> List[Employee]:
        """
        Get paginated list of employees with optional filtering.
        
        Args:
            customer_id: Customer ID for multi-tenancy
            search: Optional search term for name or email
            department_id: Optional department filter
            employment_status: Optional employment status filter
            limit: Maximum number of results
            offset: Pagination offset
            
        Returns:
            List of Employee objects with related entities loaded
        """
        context_tokens = bind_context(customer_id=customer_id)
        
        try:
            op_id = logger.start_operation(
                "list_employees",
                category=LogCategory.DATA_RETRIEVAL,
                user_message=f"Retrieving employees for customer {customer_id}",
                metadata={
                    'search': search,
                    'department_id': department_id,
                    'employment_status': employment_status,
                    'limit': limit,
                    'offset': offset
                }
            )
            
            async def operation(session):
                query = select(Employee).where(Employee.customer_id == customer_id)
                
                # Apply filters
                conditions = []
                if search:
                    search_term = f"%{search}%"
                    conditions.append(
                        or_(
                            Employee.first_name.ilike(search_term),
                            Employee.last_name.ilike(search_term),
                            Employee.email.ilike(search_term),
                            Employee.employee_number.ilike(search_term)
                        )
                    )
                
                if department_id:
                    conditions.append(Employee.department_id == department_id)
                
                if employment_status:
                    conditions.append(Employee.employment_status == employment_status)
                
                if conditions:
                    query = query.where(and_(*conditions))
                
                # Load related entities
                query = query.options(
                    selectinload(Employee.position),
                    selectinload(Employee.department),
                    selectinload(Employee.manager)
                )
                
                query = query.order_by(desc(Employee.created_at)).limit(limit).offset(offset)
                
                result = await session.execute(query)
                return list(result.scalars().all())
            
            employees = await self.execute_with_session(operation)
            
            logger.end_operation(
                op_id,
                success=True,
                items_processed=len(employees),
                user_message=f"Retrieved {len(employees)} employees"
            )
            
            return employees
            
        except Exception as e:
            logger.error(
                f"Failed to list employees",
                exception=e,
                category=LogCategory.DATA_RETRIEVAL,
                metadata={'customer_id': customer_id}
            )
            if 'op_id' in locals():
                logger.end_operation(op_id, success=False, error=str(e))
            raise
        finally:
            reset_context(context_tokens)

    async def get_employee(self, employee_id: int, customer_id: str) -> Optional[Employee]:
        """
        Get a single employee by ID with related entities.

        Args:
            employee_id: Employee ID
            customer_id: Customer ID for multi-tenancy

        Returns:
            Employee object with related entities or None if not found
        """
        context_tokens = bind_context(customer_id=customer_id, employee_id=str(employee_id))

        try:
            async def operation(session):
                query = select(Employee).where(
                    and_(
                        Employee.id == employee_id,
                        Employee.customer_id == customer_id
                    )
                ).options(
                    selectinload(Employee.position),
                    selectinload(Employee.department),
                    selectinload(Employee.manager)
                )
                result = await session.execute(query)
                return result.scalar_one_or_none()

            return await self.execute_with_session(operation)

        except Exception as e:
            logger.error(
                f"Failed to get employee {employee_id}",
                exception=e,
                category=LogCategory.DATA_RETRIEVAL,
                metadata={'employee_id': employee_id, 'customer_id': customer_id}
            )
            raise
        finally:
            reset_context(context_tokens)

    async def create_employee(self, employee: Employee) -> Employee:
        """
        Create a new employee.

        Args:
            employee: Employee object to create

        Returns:
            Created Employee object with ID
        """
        context_tokens = bind_context(customer_id=employee.customer_id)

        try:
            op_id = logger.start_operation(
                "create_employee",
                category=LogCategory.DATA_MODIFICATION,
                user_message=f"Creating employee {employee.first_name} {employee.last_name}",
                metadata={
                    'employee_number': employee.employee_number,
                    'email': employee.email
                }
            )

            async def operation(session):
                session.add(employee)
                await session.flush()
                await session.refresh(employee)
                return employee

            created_emp = await self.execute_with_session(operation)

            logger.end_operation(
                op_id,
                success=True,
                items_processed=1,
                user_message=f"Employee {created_emp.first_name} {created_emp.last_name} created successfully"
            )

            return created_emp

        except Exception as e:
            logger.error(
                f"Failed to create employee",
                exception=e,
                category=LogCategory.DATA_MODIFICATION,
                metadata={'employee_number': employee.employee_number}
            )
            if 'op_id' in locals():
                logger.end_operation(op_id, success=False, error=str(e))
            raise
        finally:
            reset_context(context_tokens)

    async def count_employees(
        self,
        customer_id: str,
        search: Optional[str] = None,
        department_id: Optional[int] = None,
        employment_status: Optional[str] = None
    ) -> int:
        """
        Count employees with optional filtering.

        Args:
            customer_id: Customer ID for multi-tenancy
            search: Optional search term
            department_id: Optional department filter
            employment_status: Optional employment status filter

        Returns:
            Total count of employees
        """
        try:
            async def operation(session):
                query = select(func.count(Employee.id)).where(Employee.customer_id == customer_id)

                conditions = []
                if search:
                    search_term = f"%{search}%"
                    conditions.append(
                        or_(
                            Employee.first_name.ilike(search_term),
                            Employee.last_name.ilike(search_term),
                            Employee.email.ilike(search_term),
                            Employee.employee_number.ilike(search_term)
                        )
                    )

                if department_id:
                    conditions.append(Employee.department_id == department_id)

                if employment_status:
                    conditions.append(Employee.employment_status == employment_status)

                if conditions:
                    query = query.where(and_(*conditions))

                result = await session.execute(query)
                return result.scalar()

            return await self.execute_with_session(operation)

        except Exception as e:
            logger.error(
                f"Failed to count employees",
                exception=e,
                category=LogCategory.DATA_RETRIEVAL,
                metadata={'customer_id': customer_id}
            )
            raise

    # ========================================================================
    # Skill Operations
    # ========================================================================

    async def list_skills(
        self,
        customer_id: str,
        category: Optional[str] = None,
        limit: int = 100,
        offset: int = 0
    ) -> List[Skill]:
        """
        Get paginated list of skills with optional filtering.

        Args:
            customer_id: Customer ID for multi-tenancy
            category: Optional category filter
            limit: Maximum number of results
            offset: Pagination offset

        Returns:
            List of Skill objects
        """
        context_tokens = bind_context(customer_id=customer_id)

        try:
            async def operation(session):
                query = select(Skill).where(Skill.customer_id == customer_id)

                if category:
                    query = query.where(Skill.category == category)

                query = query.order_by(Skill.category, Skill.name).limit(limit).offset(offset)
                result = await session.execute(query)
                return list(result.scalars().all())

            return await self.execute_with_session(operation)

        except Exception as e:
            logger.error(
                f"Failed to list skills",
                exception=e,
                category=LogCategory.DATA_RETRIEVAL,
                metadata={'customer_id': customer_id}
            )
            raise
        finally:
            reset_context(context_tokens)

    async def get_employee_skills(
        self,
        employee_id: int,
        customer_id: str
    ) -> List[EmployeeSkill]:
        """
        Get all skills for an employee.

        Args:
            employee_id: Employee ID
            customer_id: Customer ID for multi-tenancy

        Returns:
            List of EmployeeSkill objects with skill details loaded
        """
        context_tokens = bind_context(customer_id=customer_id, employee_id=str(employee_id))

        try:
            async def operation(session):
                query = select(EmployeeSkill).where(
                    and_(
                        EmployeeSkill.employee_id == employee_id,
                        EmployeeSkill.customer_id == customer_id
                    )
                ).options(
                    selectinload(EmployeeSkill.skill)
                ).order_by(EmployeeSkill.proficiency_level.desc())

                result = await session.execute(query)
                return list(result.scalars().all())

            return await self.execute_with_session(operation)

        except Exception as e:
            logger.error(
                f"Failed to get employee skills",
                exception=e,
                category=LogCategory.DATA_RETRIEVAL,
                metadata={'employee_id': employee_id, 'customer_id': customer_id}
            )
            raise
        finally:
            reset_context(context_tokens)


# Create singleton instance
hr_service = HRService()

