#!/usr/bin/env python3
"""
Create test hiring manager user for talent intelligence testing.

User:  sarah
Email: hiringmanager@eliza.com
Password: admin123
Role: Hiring Manager (with system:admin permissions for testing)
"""

import sys
import os

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.models import database
from src.models.auth import User, Role, Permission
from src.models.customer import Customer
from sqlalchemy.orm import Session
from passlib.context import CryptContext
from datetime import datetime

# Password hashing
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


def create_test_hiring_manager(db: Session):
    """Create test hiring manager user"""
    
    # Check if user already exists
    existing_user = db.query(User).filter(User.email == "hiringmanager@eliza.com").first()
    if existing_user:
        print(f"✅ Test user 'sarah' already exists (ID: {existing_user.id})")
        return existing_user
    
    # Get or create eliza customer
    customer = db.query(Customer).filter(Customer.customer_id == "eliza").first()
    if not customer:
        customer = Customer(
            customer_id="eliza",
            name="Eliza",
            contact_email="admin@eliza.com",
            is_active=True,
            created_at=datetime.utcnow()
        )
        db.add(customer)
        db.flush()
        print(f"✅ Created customer 'eliza'")
    
    # Get or create admin role
    admin_role = db.query(Role).filter(Role.name == "admin").first()
    if not admin_role:
        admin_role = Role(
            name="admin",
            description="Administrator with full permissions",
            customer_id="eliza"
        )
        db.add(admin_role)
        db.flush()
        
        # Add system:admin permission
        admin_perm = db.query(Permission).filter(Permission.name == "system:admin").first()
        if admin_perm:
            admin_role.permissions.append(admin_perm)
        
        print(f"✅ Created admin role")
    
    # Create user
    hashed_password = pwd_context.hash("admin123")
    
    user = User(
        email="hiringmanager@eliza.com",
        username="sarah",
        hashed_password=hashed_password,
        full_name="Sarah Johnson",
        customer_id="eliza",
        is_active=True,
        is_verified=True,
        created_at=datetime.utcnow()
    )
    
    # Assign admin role
    user.roles.append(admin_role)
    
    db.add(user)
    db.commit()
    db.refresh(user)
    
    print(f"✅ Created test hiring manager user:")
    print(f"   Name: Sarah Johnson")
    print(f"   Email: hiringmanager@eliza.com")
    print(f"   Password: admin123")
    print(f"   User ID: {user.id}")
    print(f"   Role: admin")
    
    return user


def main():
    # Initialize database
    if database.SessionLocal is None:
        database.init_database()
    
    db = database.SessionLocal()
    try:
        user = create_test_hiring_manager(db)
        print("\n✅ Test hiring manager ready for talent intelligence testing!")
    except Exception as e:
        print(f"❌ Error creating test user: {e}")
        db.rollback()
        raise
    finally:
        db.close()


if __name__ == "__main__":
    main()

