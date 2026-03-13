#!/usr/bin/env python3
"""Fix telemetry_event_type enum to add missing values"""
from sqlalchemy import create_engine, text
from src.core.config import get_settings

settings = get_settings()
engine = create_engine(settings.database_url)

print("Adding missing enum values to telemetry_event_type...")

with engine.connect() as conn:
    # PostgreSQL doesn't support IF NOT EXISTS for enum values directly,
    # so we need to check first
    
    # Get current enum values
    result = conn.execute(text("""
        SELECT unnest(enum_range(NULL::telemetry_event_type))::text;
    """)).fetchall()
    
    current_values = [row[0] for row in result]
    print(f"Current enum values: {current_values}")
    
    # Add missing values
    new_values = ['info', 'warning', 'error']
    
    for value in new_values:
        if value not in current_values:
            try:
                conn.execute(text(f"ALTER TYPE telemetry_event_type ADD VALUE '{value}';"))
                conn.commit()
                print(f"✅ Added '{value}' to telemetry_event_type enum")
            except Exception as e:
                if "already exists" in str(e):
                    print(f"⏭️  '{value}' already exists")
                else:
                    print(f"❌ Error adding '{value}': {e}")
        else:
            print(f"⏭️  '{value}' already exists")
    
    # Verify final state
    result = conn.execute(text("""
        SELECT unnest(enum_range(NULL::telemetry_event_type))::text;
    """)).fetchall()
    
    final_values = [row[0] for row in result]
    print(f"\nFinal enum values: {final_values}")
    print("\n✅ Enum fix complete!")

