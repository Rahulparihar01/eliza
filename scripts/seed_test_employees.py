"""
Seed test Caylent employees for ML Talent Intelligence testing.

Creates synthetic employee records in the pdl_persons table.
"""
import os
import sys
from datetime import datetime

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.models import database
from src.models.connector import PDLPerson

# Test employee data
TEST_EMPLOYEES = [
    {
        "pdl_id": "test_ml_eng_001",
        "full_name": "Sarah Chen",
        "job_title": "Senior Machine Learning Engineer",
        "job_title_role": "machine learning engineer",
        "job_company_name": "caylent",
        "skills": ["Python", "PyTorch", "TensorFlow", "MLOps", "AWS", "Kubernetes"],
        "inferred_years_experience": 8,
    },
    {
        "pdl_id": "test_ml_eng_002",
        "full_name": "Michael Rodriguez",
        "job_title": "Machine Learning Engineer",
        "job_title_role": "machine learning engineer",
        "job_company_name": "caylent",
        "skills": ["Python", "Scikit-learn", "Deep Learning", "Computer Vision", "Docker"],
        "inferred_years_experience": 5,
    },
    {
        "pdl_id": "test_ml_eng_003",
        "full_name": "Emily Watson",
        "job_title": "Staff Machine Learning Engineer",
        "job_title_role": "machine learning engineer",
        "job_company_name": "caylent",
        "skills": ["Python", "NLP", "Transformers", "Spark", "Scala", "AWS SageMaker"],
        "inferred_years_experience": 10,
    },
    {
        "pdl_id": "test_ml_eng_004",
        "full_name": "David Kim",
        "job_title": "ML Engineer",
        "job_title_role": "machine learning engineer",
        "job_company_name": "caylent",
        "skills": ["Python", "TensorFlow", "Keras", "MLflow", "Data Engineering"],
        "inferred_years_experience": 4,
    },
    {
        "pdl_id": "test_data_sci_001",
        "full_name": "Jessica Martinez",
        "job_title": "Senior Data Scientist",
        "job_title_role": "data scientist",
        "job_company_name": "caylent",
        "skills": ["Python", "R", "Statistics", "ML", "SQL", "Tableau"],
        "inferred_years_experience": 7,
    },
    {
        "pdl_id": "test_data_eng_001",
        "full_name": "Alex Thompson",
        "job_title": "Data Engineer",
        "job_title_role": "data engineer",
        "job_company_name": "caylent",
        "skills": ["Python", "Spark", "Airflow", "AWS", "SQL", "ETL"],
        "inferred_years_experience": 6,
    },
    {
        "pdl_id": "test_sw_eng_001",
        "full_name": "Chris Johnson",
        "job_title": "Software Engineer",
        "job_title_role": "software engineer",
        "job_company_name": "caylent",
        "skills": ["Python", "Java", "React", "Docker", "Kubernetes", "CI/CD"],
        "inferred_years_experience": 5,
    },
]

def main():
    """Seed test employees."""
    print(f"\n{'='*70}")
    print("SEEDING TEST CAYLENT EMPLOYEES")
    print(f"{'='*70}\n")
    
    if database.SessionLocal is None:
        database.init_database()
    
    db = database.SessionLocal()
    
    try:
        # Delete existing test employees
        print("[1/2] Cleaning up existing test data...")
        deleted = db.query(PDLPerson).filter(
            PDLPerson.pdl_id.like('test_%')
        ).delete()
        db.commit()
        print(f"   Deleted {deleted} existing test records")
        
        # Create new test employees
        print("\n[2/2] Creating test employees...")
        created_count = 0
        
        for emp_data in TEST_EMPLOYEES:
            employee = PDLPerson(
                customer_id='eliza',
                **emp_data
            )
            db.add(employee)
            created_count += 1
            print(f"   ✅ {emp_data['full_name']} - {emp_data['job_title']}")
        
        db.commit()
        
        print(f"\n{'='*70}")
        print(f"✅ SUCCESSFULLY CREATED {created_count} TEST EMPLOYEES")
        print(f"{'='*70}\n")
        
        # Show summary by role
        print("Summary by role:")
        roles = db.execute("""
            SELECT job_title_role, COUNT(*) as count
            FROM pdl_persons
            WHERE customer_id = 'eliza'
            AND job_company_name = 'caylent'
            GROUP BY job_title_role
            ORDER BY count DESC
        """)
        
        for row in roles:
            print(f"  • {row.job_title_role}: {row.count}")
        
    except Exception as e:
        print(f"\n❌ Error: {e}")
        db.rollback()
        import traceback
        traceback.print_exc()
    
    finally:
        db.close()


if __name__ == '__main__':
    main()


