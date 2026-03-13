# Database Changes

## ✅ **COMPLETED**

### **Migration: 7d0d11d0c3fc_add_company_hr_dataset_and_system_settings**

#### **File:** `alembic/versions/7d0d11d0c3fc_add_company_hr_dataset_and_system_.py`

### **Changes Made:**

#### **1. New Table: `system_settings`**
```sql
CREATE TABLE system_settings (
    id SERIAL PRIMARY KEY,
    setting_key VARCHAR(255) NOT NULL UNIQUE,
    setting_value TEXT,
    setting_type VARCHAR(50) NOT NULL DEFAULT 'string',
    description TEXT,
    is_public BOOLEAN NOT NULL DEFAULT FALSE,
    created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW()
);

CREATE INDEX ON system_settings(setting_key);
```

**Initial Data:**
```sql
INSERT INTO system_settings (setting_key, setting_value, setting_type, description, is_public)
VALUES ('default_company_hr_dataset', 'caylent', 'string', 
        'Default company for HR data queries when not explicitly specified', false);
```

#### **2. Updated Table: `bi_questions`**
```sql
ALTER TABLE bi_questions 
ADD COLUMN company_hr_dataset VARCHAR(100);

-- Backfill existing records
UPDATE bi_questions 
SET company_hr_dataset = customer_id 
WHERE company_hr_dataset IS NULL;

CREATE INDEX idx_bi_questions_company_hr_dataset ON bi_questions(company_hr_dataset);
```

### **Models Updated:**

#### **New Model: `SystemSetting`**
**File:** `src/models/system_settings.py`

```python
class SystemSetting(Base):
    __tablename__ = 'system_settings'
    
    id = Column(Integer, primary_key=True)
    setting_key = Column(String(255), nullable=False, unique=True, index=True)
    setting_value = Column(Text, nullable=True)
    setting_type = Column(String(50), nullable=False, default='string')
    description = Column(Text, nullable=True)
    is_public = Column(Boolean, nullable=False, default=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
    
    @property
    def parsed_value(self):
        """Return typed value based on setting_type"""
        # Handles: string, int, bool, json
```

#### **Updated Model: `BIQuestion`**
**File:** `src/models/business_intelligence.py`

Added field:
```python
company_hr_dataset = Column(String(100), nullable=True, index=True)
```

### **Purpose:**

- **`system_settings`**: Stores admin-configurable system defaults
- **`company_hr_dataset`**: Tracks which company's HR data each BI question targets
- **Index**: Improves query performance for company-filtered queries
- **Backfill**: Maintains backward compatibility for existing questions

### **Rollback:**

```sql
DROP INDEX idx_bi_questions_company_hr_dataset;
ALTER TABLE bi_questions DROP COLUMN company_hr_dataset;
DROP TABLE system_settings;
```

## 📝 **Field Descriptions**

| Field | Type | Purpose |
|-------|------|---------|
| `customer_id` | `VARCHAR(100)` | **Who** is asking (user's organization) |
| `company_hr_dataset` | `VARCHAR(100)` | **Whose** data to analyze (target company) |

This separation enables multi-tenant queries.

