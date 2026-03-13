# Company-Specific Data Handling - Architecture Explanation

## 🎯 **Core Concept: Separating "Who" from "What"**

The multi-tenant architecture separates two distinct concepts:
- **WHO is asking** (`customer_id`) - The user's organization
- **WHOSE data to analyze** (`company_hr_dataset`) - The target company

---

## 📊 **Database Schema**

### **Before Multi-Tenant (Old Way)**

```
User (customer_id: eliza)
  ↓
  Query → Filter by customer_id: eliza
  ↓
HR Data (customer_id: eliza)
```

**Problem**: Users could ONLY access their own organization's data.

---

### **After Multi-Tenant (New Way)**

```
User (customer_id: eliza)
  ↓
  Specifies company_hr_dataset: caylent
  ↓
  Permission Check: Does user have hr:read:company:caylent?
  ↓ YES
  Query → Filter by customer_id: caylent (NOT eliza!)
  ↓
HR Data (customer_id: caylent)
```

**Solution**: Users can access ANY company's data if they have permission.

---

## 🗂️ **Key Database Tables**

### **1. HR Data Storage (`hr_employees` table)**

```sql
CREATE TABLE hr_employees (
    id SERIAL PRIMARY KEY,
    employee_id VARCHAR(100),
    customer_id VARCHAR(100),  -- Which company this employee belongs to
    first_name VARCHAR(100),
    last_name VARCHAR(100),
    ...
);

-- Example data:
-- id | employee_id | customer_id | first_name | last_name
-- 1  | E001        | caylent     | John       | Doe
-- 2  | E002        | caylent     | Jane       | Smith
-- 3  | E003        | eliza       | Bob        | Johnson
```

**Key Point**: The `customer_id` field identifies which **company** the data belongs to, NOT which user uploaded it.

---

### **2. BI Questions (`bi_questions` table)**

```sql
CREATE TABLE bi_questions (
    id SERIAL PRIMARY KEY,
    question_id VARCHAR(100),
    user_id INTEGER,
    customer_id VARCHAR(100),          -- WHO asked (user's org)
    company_hr_dataset VARCHAR(100),   -- WHOSE data to query (target company)
    original_question TEXT,
    ...
);

-- Example data:
-- id | user_id | customer_id | company_hr_dataset | question
-- 1  | 123     | eliza       | caylent            | "Top skills in Engineering?"
-- 2  | 456     | eliza       | eliza              | "Our headcount trends?"
```

**Key Points**:
- `customer_id` = User's organization (eliza)
- `company_hr_dataset` = Target company for analysis (caylent)
- These can be DIFFERENT!

---

### **3. Documents (`documents` table)**

```sql
CREATE TABLE documents (
    id SERIAL PRIMARY KEY,
    filename VARCHAR(255),
    customer_id VARCHAR(100),          -- WHO uploaded (uploader's org)
    company_hr_dataset VARCHAR(100),   -- WHICH company this doc is about
    file_path VARCHAR(500),
    ...
);

-- Example data:
-- id | filename         | customer_id | company_hr_dataset
-- 1  | policy.pdf       | eliza       | caylent
-- 2  | handbook.pdf     | eliza       | eliza
-- 3  | training.pdf     | admin_org   | caylent
```

**Key Points**:
- User from `eliza` can upload a document about `caylent`
- Documents are stored separately and associated with target company
- FAISS index path based on `company_hr_dataset`

---

## 🔍 **How Queries Work**

### **Example 1: User from Eliza queries Caylent data**

```python
# User context
user.customer_id = "eliza"
user.permissions = ["hr:read:company:caylent"]

# BI Question submission
question = {
    "question": "What are the top skills in Engineering?",
    "company_hr_dataset": "caylent"  # User specifies target company
}

# Backend processing
1. Create question record:
   - customer_id = "eliza" (from user)
   - company_hr_dataset = "caylent" (from request)

2. Authorization check:
   - Does user have "hr:read:company:caylent"? → YES ✓

3. Query HR data:
   SELECT * FROM hr_employees 
   WHERE customer_id = 'caylent'  -- NOT 'eliza'!

4. Query documents:
   # Use FAISS index at: ./data/vectors/caylent/
   # Only search documents where company_hr_dataset = 'caylent'
```

---

### **Example 2: User with wildcard permission**

```python
# Admin user context
user.customer_id = "admin_org"
user.permissions = ["hr:read:company:*"]  # Wildcard!

# Can query ANY company
question = {
    "question": "Compare engineering teams",
    "company_hr_dataset": "caylent"  # or "eliza" or any company
}

# Backend processing
1. Authorization check:
   - Does user have "hr:read:company:caylent"? 
   - Check wildcard: "hr:read:company:*" → YES ✓

2. Query proceeds with target company's data
```

---

## 🗃️ **FAISS Vector Index Structure**

### **Directory Layout**

```
./data/vectors/
├── caylent/
│   ├── faiss_index.bin           # Caylent's document vectors
│   └── chunk_mapping.json        # Maps vectors to document chunks
├── eliza/
│   ├── faiss_index.bin           # Eliza's document vectors
│   └── chunk_mapping.json
└── [other-company]/
    ├── faiss_index.bin
    └── chunk_mapping.json
```

### **How It Works**

1. **Document Upload**:
   ```python
   # User uploads document
   document = {
       "file": policy_pdf,
       "customer_id": "eliza",          # Who uploaded
       "company_hr_dataset": "caylent"  # Which company it's about
   }
   
   # Processing
   1. Save document record in database
   2. Extract text and create chunks
   3. Generate embeddings
   4. Store in FAISS index at: ./data/vectors/caylent/
   ```

2. **Document Search**:
   ```python
   # CrewAI tool initialization
   doc_tool = DocumentSearchTool(
       customer_id="eliza",          # User's org (for audit)
       company_hr_dataset="caylent"  # Which company's docs to search
   )
   
   # Tool uses VectorService
   vector_service = VectorService(company_hr_dataset="caylent")
   # Loads index from: ./data/vectors/caylent/
   ```

---

## 🔐 **Permission System**

### **Permission Format**

```
hr:read:company:{company_id}
```

**Examples**:
- `hr:read:company:*` - Access ALL companies (wildcard)
- `hr:read:company:caylent` - Access Caylent only
- `hr:read:company:eliza` - Access Eliza only

### **Role Assignments**

```python
# Super Admin
permissions = [
    "hr:read:company:*",      # All companies
    "bi:read", "bi:write", "bi:admin",
    "settings:read", "settings:write"
]

# Manager at Eliza
permissions = [
    "hr:read:company:eliza",  # Only their own company
    "bi:read", "bi:write"
]

# Analyst with special access
permissions = [
    "hr:read:company:caylent",  # Can access Caylent
    "hr:read:company:eliza",    # Can access Eliza
    "bi:read", "bi:write"
]
```

---

## 🔄 **Complete Data Flow**

### **BI Question Pipeline**

```
1. Frontend Submission
   ↓
   POST /v1/bi/questions
   {
     "question": "Top skills?",
     "company_hr_dataset": "caylent"  // Optional
   }

2. API Layer (business_intelligence.py)
   ↓
   - Determine company (use request value or system default)
   - Check authorization: user has hr:read:company:caylent?
   - Create question record:
     * customer_id = user.customer_id
     * company_hr_dataset = "caylent"

3. Celery Task (business_intelligence_tasks.py)
   ↓
   - Receive: question_id, customer_id, company_hr_dataset
   - Check connectivity to target company's data
   - Pass to CrewAI flows

4. CrewAI Flow (data_analysis_flow.py)
   ↓
   - Initialize tools with company_hr_dataset
   - HRDatabaseTool(customer_id="caylent")
   - DocumentSearchTool(company_hr_dataset="caylent")

5. Tool Execution
   ↓
   HR Tool:
     SELECT * FROM hr_employees 
     WHERE customer_id = 'caylent'
   
   Document Tool:
     Load FAISS index from ./data/vectors/caylent/
     Search documents where company_hr_dataset = 'caylent'

6. Return Results
   ↓
   Response contains data from Caylent (target company)
   Audit log records: user from 'eliza' queried 'caylent' data
```

---

## 📋 **Database Queries Examples**

### **Query 1: Get all companies with data**

```sql
-- List all companies that have HR data
SELECT DISTINCT customer_id, COUNT(*) as employee_count
FROM hr_employees
GROUP BY customer_id;

-- Result:
-- customer_id | employee_count
-- caylent     | 150
-- eliza       | 75
```

### **Query 2: Check user's accessible companies**

```sql
-- Check which companies user can access
SELECT p.name as permission
FROM users u
JOIN user_roles ur ON u.id = ur.user_id
JOIN role_permissions rp ON ur.role_id = rp.role_id
JOIN permissions p ON rp.permission_id = p.id
WHERE u.id = 123
  AND p.resource = 'hr_data'
  AND p.action = 'read';

-- Result:
-- permission
-- hr:read:company:*
-- (User can access all companies)
```

### **Query 3: Get documents for a company**

```sql
-- Get all documents associated with Caylent
SELECT id, filename, customer_id as uploader, company_hr_dataset as target_company
FROM documents
WHERE company_hr_dataset = 'caylent';

-- Result:
-- id | filename     | uploader | target_company
-- 1  | policy.pdf   | eliza    | caylent
-- 2  | handbook.pdf | admin    | caylent
```

### **Query 4: Get BI questions by target company**

```sql
-- See which users are querying Caylent data
SELECT 
    q.question_id,
    u.email as user_email,
    q.customer_id as user_org,
    q.company_hr_dataset as target_company,
    q.original_question
FROM bi_questions q
JOIN users u ON q.user_id = u.id
WHERE q.company_hr_dataset = 'caylent'
ORDER BY q.created_at DESC;

-- Result shows cross-company queries with full audit trail
```

---

## 🎯 **Key Takeaways**

### **1. Two IDs for Everything**
- `customer_id` = Owner/Actor (who did it)
- `company_hr_dataset` = Target (which company's data)

### **2. Data is Stored by Company**
- HR data: `customer_id` field identifies the company
- Documents: `company_hr_dataset` identifies the company
- FAISS indexes: Separate directory per company

### **3. Queries Filter by Target, Not User**
```python
# WRONG (old way)
query = f"SELECT * FROM hr_employees WHERE customer_id = '{user.customer_id}'"

# CORRECT (new way)
query = f"SELECT * FROM hr_employees WHERE customer_id = '{question.company_hr_dataset}'"
```

### **4. Permissions Enforce Access**
- User must have `hr:read:company:{target_company}` permission
- Wildcard `hr:read:company:*` grants access to all companies
- Authorization checked BEFORE query execution

### **5. Complete Data Isolation**
- Each company's FAISS index is separate
- No cross-contamination possible
- Documents and embeddings isolated by company

---

## 🔍 **Verification Queries**

Run these to verify your multi-tenant setup:

```sql
-- 1. Check HR data distribution
SELECT customer_id, COUNT(*) as employees
FROM hr_employees
GROUP BY customer_id;

-- 2. Check document distribution
SELECT company_hr_dataset, COUNT(*) as documents
FROM documents
GROUP BY company_hr_dataset;

-- 3. Check BI question patterns
SELECT 
    customer_id as user_org,
    company_hr_dataset as target_org,
    COUNT(*) as questions
FROM bi_questions
GROUP BY customer_id, company_hr_dataset;

-- 4. Verify system default
SELECT setting_value 
FROM system_settings 
WHERE setting_key = 'default_company_hr_dataset';
```

---

## ✅ **Summary**

The architecture enables:
- ✅ Users from one organization can query another organization's data
- ✅ Permissions control which companies a user can access
- ✅ Data is completely isolated (HR, documents, vector indexes)
- ✅ Full audit trail of who accessed what
- ✅ Flexible permission grants (wildcard or specific)
- ✅ System defaults for convenience
- ✅ Backward compatible (defaults to user's own org)

**Think of it like this**: It's like having multiple databases, but with a single interface where permissions determine which "databases" (companies) you can query.

