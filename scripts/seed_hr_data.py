"""
Seed HR Data Script

This script generates realistic seed data for 150 Caylent employees with:
- Varied roles across departments (Engineering, Sales, Customer Success, Operations, Leadership)
- Skills aligned with Caylent's AWS/cloud focus
- Proper referential integrity across all tables
- Realistic organizational hierarchy
"""

import asyncio
import sys
import os
from datetime import date, datetime, timedelta
from decimal import Decimal
import random

# Add parent directory to path for imports
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from src.models import init_async_database
import src.models
from src.models.hr import (
    Department, Position, Employee, Skill, EmployeeSkill,
    PerformanceReview, TrainingProgram, EmployeeTrainingRecord,
    Certification, Compensation,
    EmploymentStatus, EmploymentType, WorkLocation
)

# Customer ID for seed data
CUSTOMER_ID = "caylent"

# ============================================================================
# Data Definitions
# ============================================================================

DEPARTMENTS = [
    {"name": "Engineering", "code": "ENG", "description": "Cloud engineering and architecture"},
    {"name": "Sales", "code": "SALES", "description": "Sales and business development"},
    {"name": "Customer Success", "code": "CS", "description": "Customer success and support"},
    {"name": "Operations", "code": "OPS", "description": "HR, Finance, IT, Admin"},
    {"name": "Leadership", "code": "LEAD", "description": "Executive leadership"},
]

POSITIONS = [
    # Engineering positions (60-65% of workforce)
    {"title": "Cloud Architect", "level": "Senior", "job_family": "Engineering", "count": 15},
    {"title": "Cloud Architect", "level": "Staff", "job_family": "Engineering", "count": 8},
    {"title": "Cloud Architect", "level": "Principal", "job_family": "Engineering", "count": 3},
    {"title": "DevOps Engineer", "level": "Mid", "job_family": "Engineering", "count": 12},
    {"title": "DevOps Engineer", "level": "Senior", "job_family": "Engineering", "count": 10},
    {"title": "Data Engineer", "level": "Mid", "job_family": "Engineering", "count": 8},
    {"title": "Data Engineer", "level": "Senior", "job_family": "Engineering", "count": 6},
    {"title": "Security Engineer", "level": "Senior", "job_family": "Engineering", "count": 5},
    {"title": "Solutions Architect", "level": "Senior", "job_family": "Engineering", "count": 10},
    {"title": "ML Engineer", "level": "Senior", "job_family": "Engineering", "count": 4},
    {"title": "Engineering Manager", "level": "Manager", "job_family": "Engineering", "count": 5},
    
    # Sales & Customer Success (15-20%)
    {"title": "Account Executive", "level": "Senior", "job_family": "Sales", "count": 8},
    {"title": "Solutions Architect", "level": "Senior", "job_family": "Sales", "count": 6},
    {"title": "Sales Manager", "level": "Manager", "job_family": "Sales", "count": 2},
    {"title": "Customer Success Manager", "level": "Senior", "job_family": "Customer Success", "count": 10},
    {"title": "Technical Account Manager", "level": "Senior", "job_family": "Customer Success", "count": 6},
    
    # Operations (10-15%)
    {"title": "HR Manager", "level": "Manager", "job_family": "Operations", "count": 2},
    {"title": "Finance Manager", "level": "Manager", "job_family": "Operations", "count": 2},
    {"title": "IT Administrator", "level": "Mid", "job_family": "Operations", "count": 3},
    {"title": "Operations Coordinator", "level": "Mid", "job_family": "Operations", "count": 4},
    {"title": "Recruiter", "level": "Mid", "job_family": "Operations", "count": 3},
    
    # Leadership (5%)
    {"title": "VP Engineering", "level": "VP", "job_family": "Leadership", "count": 1},
    {"title": "VP Sales", "level": "VP", "job_family": "Leadership", "count": 1},
    {"title": "VP Customer Success", "level": "VP", "job_family": "Leadership", "count": 1},
    {"title": "VP Operations", "level": "VP", "job_family": "Leadership", "count": 1},
    {"title": "CTO", "level": "C-Level", "job_family": "Leadership", "count": 1},
    {"title": "CEO", "level": "C-Level", "job_family": "Leadership", "count": 1},
    {"title": "CFO", "level": "C-Level", "job_family": "Leadership", "count": 1},
]

# Caylent-specific skills aligned with their business
SKILLS = [
    # AWS Certifications
    {"name": "AWS Solutions Architect - Professional", "category": "AWS Certification"},
    {"name": "AWS Solutions Architect - Associate", "category": "AWS Certification"},
    {"name": "AWS DevOps Engineer - Professional", "category": "AWS Certification"},
    {"name": "AWS Security - Specialty", "category": "AWS Certification"},
    {"name": "AWS Data Analytics - Specialty", "category": "AWS Certification"},
    {"name": "AWS Machine Learning - Specialty", "category": "AWS Certification"},
    {"name": "AWS Advanced Networking - Specialty", "category": "AWS Certification"},
    
    # AWS Services
    {"name": "Amazon EC2", "category": "AWS Compute"},
    {"name": "Amazon ECS/EKS", "category": "AWS Compute"},
    {"name": "AWS Lambda", "category": "AWS Compute"},
    {"name": "Amazon S3", "category": "AWS Storage"},
    {"name": "Amazon RDS", "category": "AWS Database"},
    {"name": "Amazon DynamoDB", "category": "AWS Database"},
    {"name": "Amazon Redshift", "category": "AWS Data"},
    {"name": "AWS Glue", "category": "AWS Data"},
    {"name": "Amazon SageMaker", "category": "AWS AI/ML"},
    {"name": "Amazon Bedrock", "category": "AWS AI/ML"},
    {"name": "AWS Control Tower", "category": "AWS Governance"},
    {"name": "AWS Organizations", "category": "AWS Governance"},
    {"name": "AWS CloudFormation", "category": "AWS IaC"},
    
    # DevOps & IaC
    {"name": "Terraform", "category": "Infrastructure as Code"},
    {"name": "Ansible", "category": "Configuration Management"},
    {"name": "Kubernetes", "category": "Container Orchestration"},
    {"name": "Docker", "category": "Containerization"},
    {"name": "Jenkins", "category": "CI/CD"},
    {"name": "GitLab CI/CD", "category": "CI/CD"},
    {"name": "GitHub Actions", "category": "CI/CD"},
    
    # Programming Languages
    {"name": "Python", "category": "Programming Language"},
    {"name": "Go", "category": "Programming Language"},
    {"name": "Java", "category": "Programming Language"},
    {"name": "TypeScript", "category": "Programming Language"},
    
    # Data & Analytics
    {"name": "Apache Spark", "category": "Data Processing"},
    {"name": "Apache Airflow", "category": "Data Orchestration"},
    {"name": "dbt", "category": "Data Transformation"},
    
    # Security
    {"name": "AWS Security Hub", "category": "Security"},
    {"name": "AWS GuardDuty", "category": "Security"},
    {"name": "HashiCorp Vault", "category": "Security"},
    
    # Soft Skills
    {"name": "Cloud Architecture Design", "category": "Architecture"},
    {"name": "Technical Leadership", "category": "Leadership"},
    {"name": "Customer Communication", "category": "Communication"},
    {"name": "Project Management", "category": "Management"},
]

TRAINING_PROGRAMS = [
    {"program_name": "AWS Solutions Architect Certification Prep", "program_code": "AWS-SA-CERT", "provider": "A Cloud Guru", "category": "technical", "duration_hours": 40.0, "delivery_method": "self_paced", "cost_per_participant": 299.00},
    {"program_name": "AWS DevOps Engineer Certification Prep", "program_code": "AWS-DO-CERT", "provider": "A Cloud Guru", "category": "technical", "duration_hours": 35.0, "delivery_method": "self_paced", "cost_per_participant": 299.00},
    {"program_name": "Kubernetes Administration", "program_code": "K8S-ADMIN", "provider": "Linux Foundation", "category": "technical", "duration_hours": 30.0, "delivery_method": "virtual", "cost_per_participant": 399.00},
    {"program_name": "Terraform Deep Dive", "program_code": "TF-DEEP", "provider": "HashiCorp", "category": "technical", "duration_hours": 20.0, "delivery_method": "virtual", "cost_per_participant": 199.00},
    {"program_name": "AWS Security Best Practices", "program_code": "AWS-SEC-BP", "provider": "AWS Training", "category": "technical", "duration_hours": 16.0, "delivery_method": "self_paced", "cost_per_participant": 0.00},
    {"program_name": "Data Engineering on AWS", "program_code": "AWS-DATA-ENG", "provider": "AWS Training", "category": "technical", "duration_hours": 24.0, "delivery_method": "self_paced", "cost_per_participant": 0.00},
    {"program_name": "Machine Learning on AWS", "program_code": "AWS-ML", "provider": "Coursera", "category": "technical", "duration_hours": 40.0, "delivery_method": "self_paced", "cost_per_participant": 49.00},
    {"program_name": "Leadership Fundamentals", "program_code": "LEAD-FUND", "provider": "Internal", "category": "leadership", "duration_hours": 8.0, "delivery_method": "in_person", "cost_per_participant": 0.00, "is_mandatory": True},
]

# First names pool
FIRST_NAMES = [
    "James", "Mary", "John", "Patricia", "Robert", "Jennifer", "Michael", "Linda",
    "William", "Elizabeth", "David", "Barbara", "Richard", "Susan", "Joseph", "Jessica",
    "Thomas", "Sarah", "Charles", "Karen", "Christopher", "Nancy", "Daniel", "Lisa",
    "Matthew", "Betty", "Anthony", "Margaret", "Mark", "Sandra", "Donald", "Ashley",
    "Steven", "Kimberly", "Paul", "Emily", "Andrew", "Donna", "Joshua", "Michelle",
    "Kenneth", "Dorothy", "Kevin", "Carol", "Brian", "Amanda", "George", "Melissa",
    "Edward", "Deborah", "Ronald", "Stephanie", "Timothy", "Rebecca", "Jason", "Sharon",
    "Jeffrey", "Laura", "Ryan", "Cynthia", "Jacob", "Kathleen", "Gary", "Amy",
    "Nicholas", "Shirley", "Eric", "Angela", "Jonathan", "Helen", "Stephen", "Anna",
    "Larry", "Brenda", "Justin", "Pamela", "Scott", "Nicole", "Brandon", "Emma",
    "Benjamin", "Samantha", "Samuel", "Katherine", "Raymond", "Christine", "Gregory", "Debra",
    "Frank", "Rachel", "Alexander", "Catherine", "Patrick", "Carolyn", "Jack", "Janet",
    "Dennis", "Ruth", "Jerry", "Maria", "Tyler", "Heather", "Aaron", "Diane",
]

# Last names pool
LAST_NAMES = [
    "Smith", "Johnson", "Williams", "Brown", "Jones", "Garcia", "Miller", "Davis",
    "Rodriguez", "Martinez", "Hernandez", "Lopez", "Gonzalez", "Wilson", "Anderson", "Thomas",
    "Taylor", "Moore", "Jackson", "Martin", "Lee", "Perez", "Thompson", "White",
    "Harris", "Sanchez", "Clark", "Ramirez", "Lewis", "Robinson", "Walker", "Young",
    "Allen", "King", "Wright", "Scott", "Torres", "Nguyen", "Hill", "Flores",
    "Green", "Adams", "Nelson", "Baker", "Hall", "Rivera", "Campbell", "Mitchell",
    "Carter", "Roberts", "Gomez", "Phillips", "Evans", "Turner", "Diaz", "Parker",
    "Cruz", "Edwards", "Collins", "Reyes", "Stewart", "Morris", "Morales", "Murphy",
    "Cook", "Rogers", "Gutierrez", "Ortiz", "Morgan", "Cooper", "Peterson", "Bailey",
    "Reed", "Kelly", "Howard", "Ramos", "Kim", "Cox", "Ward", "Richardson",
    "Watson", "Brooks", "Chavez", "Wood", "James", "Bennett", "Gray", "Mendoza",
    "Ruiz", "Hughes", "Price", "Alvarez", "Castillo", "Sanders", "Patel", "Myers",
]


async def create_seed_data():
    """Create all seed data for HR system"""
    
    # Initialize async database
    init_async_database()
    AsyncSessionLocal = src.models.AsyncSessionLocal
    
    async with AsyncSessionLocal() as session:
        try:
            print("🌱 Starting HR seed data creation for Caylent...")
            print(f"   Using customer_id: {CUSTOMER_ID}")

            # Create departments
            print("\n📁 Creating departments...")
            dept_objects = []
            for dept_data in DEPARTMENTS:
                dept = Department(
                    customer_id=CUSTOMER_ID,
                    **dept_data
                )
                session.add(dept)
                dept_objects.append(dept)
            
            await session.flush()
            print(f"✅ Created {len(dept_objects)} departments")
            
            # Create department mapping
            dept_map = {d.code: d for d in dept_objects}
            
            # Create positions
            print("\n💼 Creating positions...")
            position_objects = []
            for pos_data in POSITIONS:
                # Find department for this job family
                dept_code_map = {
                    "Engineering": "ENG",
                    "Sales": "SALES",
                    "Customer Success": "CS",
                    "Operations": "OPS",
                    "Leadership": "LEAD"
                }
                dept_code = dept_code_map.get(pos_data["job_family"], "OPS")
                
                position = Position(
                    customer_id=CUSTOMER_ID,
                    title=pos_data["title"],
                    level=pos_data["level"],
                    job_family=pos_data["job_family"],
                    description=f"{pos_data['title']} - {pos_data['level']} level position",
                    is_active=True
                )
                session.add(position)
                position_objects.append((position, pos_data["count"]))
            
            await session.flush()
            print(f"✅ Created {len(position_objects)} position types")
            
            # Create skills
            print("\n🎯 Creating skills...")
            skill_objects = []
            for skill_data in SKILLS:
                skill = Skill(
                    customer_id=CUSTOMER_ID,
                    **skill_data
                )
                session.add(skill)
                skill_objects.append(skill)
            
            await session.flush()
            print(f"✅ Created {len(skill_objects)} skills")
            
            print("\n👥 Creating 150 employees...")
            employee_objects = []
            employee_count = 0
            used_emails = set()

            # Create employees based on position counts
            for position, count in position_objects:
                for i in range(count):
                    # Generate unique name and email
                    first_name = random.choice(FIRST_NAMES)
                    last_name = random.choice(LAST_NAMES)
                    email = f"{first_name.lower()}.{last_name.lower()}@caylent.com"

                    # Ensure unique email
                    counter = 1
                    while email in used_emails:
                        email = f"{first_name.lower()}.{last_name.lower()}{counter}@caylent.com"
                        counter += 1
                    used_emails.add(email)

                    # Generate hire date (between 6 months and 5 years ago)
                    days_ago = random.randint(180, 1825)
                    hire_date = date.today() - timedelta(days=days_ago)

                    # Determine department
                    dept_code_map = {
                        "Engineering": "ENG",
                        "Sales": "SALES",
                        "Customer Success": "CS",
                        "Operations": "OPS",
                        "Leadership": "LEAD"
                    }
                    dept_code = dept_code_map.get(position.job_family, "OPS")
                    department = dept_map[dept_code]

                    # Create employee
                    employee_count += 1
                    employee = Employee(
                        customer_id=CUSTOMER_ID,
                        employee_number=f"EMP{employee_count:04d}",
                        first_name=first_name,
                        last_name=last_name,
                        email=email,
                        phone=f"+1-555-{random.randint(1000, 9999)}",
                        hire_date=hire_date,
                        employment_status=EmploymentStatus.ACTIVE,
                        employment_type=EmploymentType.FULL_TIME,
                        work_location=random.choice([WorkLocation.REMOTE, WorkLocation.HYBRID, WorkLocation.OFFICE]),
                        position_id=position.id,
                        department_id=department.id,
                        manager_id=None  # Will set managers in second pass
                    )
                    session.add(employee)
                    employee_objects.append(employee)

            await session.flush()
            print(f"✅ Created {len(employee_objects)} employees")

            # Set managers (second pass)
            print("\n👔 Assigning managers...")
            # Leadership reports to CEO
            ceo = next((e for e in employee_objects if "CEO" in e.position.title), None)

            # VPs report to CEO
            vps = [e for e in employee_objects if "VP" in e.position.title]
            for vp in vps:
                if vp != ceo:
                    vp.manager_id = ceo.id

            # Managers report to VPs
            eng_vp = next((e for e in vps if "Engineering" in e.position.title), None)
            sales_vp = next((e for e in vps if "Sales" in e.position.title), None)
            cs_vp = next((e for e in vps if "Customer Success" in e.position.title), None)
            ops_vp = next((e for e in vps if "Operations" in e.position.title), None)

            managers = [e for e in employee_objects if "Manager" in e.position.title]
            for manager in managers:
                if "Engineering" in manager.position.job_family and eng_vp:
                    manager.manager_id = eng_vp.id
                elif "Sales" in manager.position.job_family and sales_vp:
                    manager.manager_id = sales_vp.id
                elif "Customer Success" in manager.position.job_family and cs_vp:
                    manager.manager_id = cs_vp.id
                elif "Operations" in manager.position.job_family and ops_vp:
                    manager.manager_id = ops_vp.id

            # Individual contributors report to managers
            eng_managers = [m for m in managers if "Engineering" in m.position.job_family]
            sales_managers = [m for m in managers if "Sales" in m.position.job_family]

            for employee in employee_objects:
                if employee.manager_id is None and "Manager" not in employee.position.title and "VP" not in employee.position.title and "CEO" not in employee.position.title:
                    if "Engineering" in employee.position.job_family and eng_managers:
                        employee.manager_id = random.choice(eng_managers).id
                    elif "Sales" in employee.position.job_family and sales_managers:
                        employee.manager_id = random.choice(sales_managers).id
                    elif "Customer Success" in employee.position.job_family and cs_vp:
                        employee.manager_id = cs_vp.id
                    elif "Operations" in employee.position.job_family and ops_vp:
                        employee.manager_id = ops_vp.id

            await session.flush()
            print(f"✅ Assigned managers to employees")

            # Assign skills to employees
            print("\n🎯 Assigning skills to employees...")
            skill_count = 0
            for employee in employee_objects:
                # Number of skills based on seniority
                if "Senior" in employee.position.level or "Staff" in employee.position.level:
                    num_skills = random.randint(8, 15)
                elif "Principal" in employee.position.level or "Manager" in employee.position.level:
                    num_skills = random.randint(10, 18)
                elif "VP" in employee.position.level or "C-Level" in employee.position.level:
                    num_skills = random.randint(12, 20)
                else:
                    num_skills = random.randint(5, 10)

                # Select random skills
                selected_skills = random.sample(skill_objects, min(num_skills, len(skill_objects)))

                for skill in selected_skills:
                    # Proficiency based on seniority
                    if "Senior" in employee.position.level or "Staff" in employee.position.level:
                        proficiency = random.choice(["advanced", "expert", "expert"])
                    elif "Principal" in employee.position.level or "Manager" in employee.position.level:
                        proficiency = random.choice(["expert", "expert", "advanced"])
                    else:
                        proficiency = random.choice(["intermediate", "advanced", "intermediate"])

                    employee_skill = EmployeeSkill(
                        customer_id=CUSTOMER_ID,
                        employee_id=employee.id,
                        skill_id=skill.id,
                        proficiency_level=proficiency,
                        years_experience=random.uniform(1.0, 10.0),
                        last_used_date=date.today() - timedelta(days=random.randint(0, 90))
                    )
                    session.add(employee_skill)
                    skill_count += 1

            await session.flush()
            print(f"✅ Assigned {skill_count} skills to employees")

            # Create training programs
            print("\n📚 Creating training programs...")
            training_objects = []
            for training_data in TRAINING_PROGRAMS:
                training = TrainingProgram(
                    customer_id=CUSTOMER_ID,
                    **training_data
                )
                session.add(training)
                training_objects.append(training)

            await session.flush()
            print(f"✅ Created {len(training_objects)} training programs")

            await session.commit()
            print("\n✅ Seed data creation completed successfully!")
            print(f"\n📊 Summary:")
            print(f"   - Departments: {len(dept_objects)}")
            print(f"   - Positions: {len(position_objects)}")
            print(f"   - Employees: {len(employee_objects)}")
            print(f"   - Skills: {len(skill_objects)}")
            print(f"   - Employee Skills: {skill_count}")
            print(f"   - Training Programs: {len(training_objects)}")
            
        except Exception as e:
            await session.rollback()
            print(f"\n❌ Error creating seed data: {str(e)}")
            import traceback
            traceback.print_exc()
            raise


if __name__ == "__main__":
    asyncio.run(create_seed_data())

