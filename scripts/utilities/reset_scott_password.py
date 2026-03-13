#!/usr/bin/env python3
"""Reset scott@eliza.com password"""
from sqlalchemy import create_engine, text
from src.core.config import get_settings
from passlib.context import CryptContext

settings = get_settings()
engine = create_engine(settings.database_url)

# Password hasher
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

# New password
new_password = "password123"

with engine.connect() as conn:
    # Get user
    result = conn.execute(text("SELECT id, email FROM users WHERE email = 'scott@eliza.com'")).fetchone()
    
    if result:
        user_id = result[0]
        email = result[1]
        
        # Hash the password
        hashed = pwd_context.hash(new_password)
        
        # Update password
        conn.execute(
            text("UPDATE users SET hashed_password = :pwd WHERE id = :uid"),
            {"pwd": hashed, "uid": user_id}
        )
        conn.commit()
        
        print(f"✅ Password reset for {email}")
        print(f"   Email: scott@eliza.com")
        print(f"   Password: {new_password}")
    else:
        print("❌ User not found!")
