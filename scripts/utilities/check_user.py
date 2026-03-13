#!/usr/bin/env python3
"""Quick script to check if scott@eliza.com user exists"""
from sqlalchemy import create_engine, text
from src.core.config import get_settings

settings = get_settings()
engine = create_engine(settings.database_url)

with engine.connect() as conn:
    # Check user
    result = conn.execute(text("SELECT email, customer_id, is_active, is_superuser FROM users WHERE email = 'scott@eliza.com'")).fetchone()
    
    if result:
        print(f"✅ User exists!")
        print(f"   Email: {result[0]}")
        print(f"   Customer: {result[1]}")
        print(f"   Active: {result[2]}")
        print(f"   Superuser: {result[3]}")
        
        # Check roles
        user_id_result = conn.execute(text("SELECT id FROM users WHERE email = 'scott@eliza.com'")).fetchone()
        if user_id_result:
            user_id = user_id_result[0]
            roles = conn.execute(text("""
                SELECT r.display_name, r.name 
                FROM roles r 
                JOIN user_roles ur ON r.id = ur.role_id 
                WHERE ur.user_id = :user_id
            """), {"user_id": user_id}).fetchall()
            
            if roles:
                print(f"\n   Roles:")
                for role in roles:
                    print(f"     • {role[0]} ({role[1]})")
            else:
                print(f"\n   ⚠️  No roles assigned!")
    else:
        print("❌ User NOT found!")

